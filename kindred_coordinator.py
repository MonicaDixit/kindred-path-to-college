"""
Coordinator - deterministic orchestrator (NO LLM).

Responsibilities (Checkpoint 5, section 4):
  1. Classify the student's query into an intent.
  2. Extract entities (profile fields, college names, essay text) with plain Python.
  3. Update shared state.
  4. Decide which specialized agent node runs next (`route`).
  5. After an agent runs, format nothing extra - agents write `response` directly;
     the Coordinator just records the exchange in `messages`.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Tuple

import audit_log
import college_repo
import guardrails
import guardrail_classifier
from kindred_state import KindredState

# ---------------------------------------------------------------------------
# Intent classification
# ---------------------------------------------------------------------------

INTENTS = (
    "crisis",
    "emotional_support",
    "missed_deadline",
    "scholarship_rejection",
    "resume",
    "out_of_scope",
    "human_handoff",
    "confirm_profile",
    "deadline_planning",
    "essay_help",
    "essay_guidance",
    "essay_followup",
    "college_inquiry",
    "college_discovery",
    "discovery_followup",
    "profile_update",
    "help",
)

_PLANNING_KW = (
    "plan my week", "plan my", "week-by-week", "week by week", "timeline",
    "deadline order", "what order", "schedule", "organize my", "when should i",
    "how do i plan", "priorit",
)
_ESSAY_DRAFT_RE = re.compile(
    r"(here'?s?\s+(?:my|the|a|what i wrote)\b[^.]{0,40}\b(essay|draft|statement|"
    r"paragraph|response)"
    r"|\b(?:my|the)\s+(?:\w+\s+){0,2}(?:essay\s+)?draft\b"
    r"|i wrote (?:my|this|the following)"
    r"|review my (?:essay|draft|writing|personal statement)"
    r"|feedback on (?:my|this)\s+(?:essay|draft|writing)"
    r"|(?:revised|second|third|new)\s+draft|draft\s*[#]?\s*[2-9]"
    r"|what do you think of (?:my|this))",
    re.I,
)
_ESSAY_GUIDANCE_KW = (
    "essay", "personal statement", "supplemental", "common app", "prompt",
    "brainstorm", "what should i write",
)
_DISCOVERY_KW = (
    "college", "colleges", "school", "schools", "university", "universities",
    "recommend", "recommendation", "match me", "find me", "give me a", "give me some",
    "college list", "school list", "my list", "a list of colleges", "shortlist",
    "reach school", "target school", "safety school", "where should i apply",
    "where to apply", "college options", "add ", "remove ", "swap",
)
_INQUIRY_KW = (
    "tell me about", "what about", "more about", "deadline", "acceptance rate",
    "how selective", "what's the", "whats the", "info on", "details on",
    "cost", "how much", "tuition", "price", "afford", "financial aid", "aid",
    "scholarship", "chances", "get in", "getting in", "compare", " vs ", "versus",
    "majors", "programs", "campus", "student life", "ranking", "ranked",
    "first-gen support", "why did you", "why these", "why those", "which one",
    "which of these", "best fit", "better for me",
)

# Explicit requests for the capabilities menu.
_HELP_TEXT = {"help", "menu", "start", "?", "hi", "hello", "hey", "yo", "sup"}
_HELP_PHRASES = ("what can you do", "what do you do", "how does this work",
                 "who are you", "what are you")

# Backwards-compatible alias - the deterministic distress check now lives in
# guardrails.py (this returns 'crisis' / 'distress' / '').
safety_signal = guardrails.distress_signal

_HUMAN_REQUEST = re.compile(
    r"(connect me (?:with |to )?(?:an? )?(?:\w+ ){0,2}(?:human|advisor|counsel|person)"
    r"|(?:talk|speak) (?:to|with) (?:an? )?(?:\w+ ){0,2}(?:human|person|counsel|advisor|"
    r"someone|real person)"
    r"|(?:want|need|like) to (?:talk|speak) (?:to|with) (?:a |an )?(?:real |actual )?"
    r"(?:human|person|counsel|advisor|someone)"
    r"|get me a (?:human|person|counsel)"
    r"|is there a (?:human|person|real person|counsel))",
    re.I,
)

# When a query matches no rule but we're mid-conversation, keep the student
# with the specialist they were already talking to instead of the help menu.
_STICKY_INTENT = {
    "discovery": "discovery_followup",
    "essay": "essay_followup",
    "planning": "deadline_planning",
    "support": None,          # never stick to support - use awaiting_resume instead
    "respond": None,
}


def classify_intent(text: str, prior_state: KindredState) -> str:
    """Task-intent classification (safety routing is handled in coordinator_node).
    `prior_state` is the shared state as it was BEFORE this turn."""
    t = text.lower().strip()
    colleges = college_repo.resolve(t)
    in_conversation = bool(prior_state.get("messages"))
    prior_route = prior_state.get("route", "respond")
    # A real pasted essay draft is long AND signalled as an essay / in an essay
    # thread - a real pasted draft is prose-y (several sentences, first person)
    # and either says so or is long / in an essay thread.
    sentences = text.count(".") + text.count("!") + text.count("?")
    prose_like = len(text) > 320 and sentences >= 3 and re.search(r"\bi\b|\bmy\b", t)
    looks_like_draft = (
        _ESSAY_DRAFT_RE.search(text)
        or (prose_like and ("essay" in t or "draft" in t or "personal statement" in t
                            or prior_route == "essay"))
        or len(text) > 700
    )

    # 0c. explicit greeting / "what can you do" -> menu (even mid-conversation)
    if t.rstrip("!.") in _HELP_TEXT or any(p in t for p in _HELP_PHRASES):
        return "help"

    # 1. deadline planning
    if any(k in t for k in _PLANNING_KW):
        return "deadline_planning"

    # 2. pasted essay draft
    if looks_like_draft:
        return "essay_help"

    # 3. essay guidance
    if "essay" in t or "personal statement" in t or "supplemental" in t:
        return "essay_guidance"

    # 4. question about a named college
    if colleges and any(k in t for k in _INQUIRY_KW):
        return "college_inquiry"

    # 4b. opinion / explanation follow-up mid-conversation ("why those?", "which
    #     one is best?", "how much does it cost?") -> stay with the last specialist
    if in_conversation and any(k in t for k in _INQUIRY_KW):
        sticky = _STICKY_INTENT.get(prior_route)
        if sticky:
            return sticky

    # 5. college-search language
    if any(k in t for k in _DISCOVERY_KW):
        return "college_discovery"

    # 6. bare profile info -> discovery seed / refinement
    if _extract_profile(text)[0]:
        return "college_discovery"

    # 7. bare college name
    if colleges:
        return "college_inquiry"

    # 8. STICKY: any other ambiguous follow-up -> stay with the last specialist
    if in_conversation:
        sticky = _STICKY_INTENT.get(prior_route)
        if sticky:
            return sticky

    # 9. first turn / genuinely unclassifiable
    return "help"


_INTENT_TO_ROUTE = {
    "crisis": "support",
    "emotional_support": "support",
    "missed_deadline": "support",
    "scholarship_rejection": "support",
    "resume": "respond",
    "out_of_scope": "respond",
    "human_handoff": "respond",
    "confirm_profile": "respond",
    "deadline_planning": "planning",
    "essay_help": "essay",
    "essay_guidance": "essay",
    "essay_followup": "essay",
    "college_inquiry": "discovery",
    "college_discovery": "discovery",
    "discovery_followup": "discovery",
    "profile_update": "discovery",
    "help": "respond",
}


def route_for(intent: str) -> str:
    return _INTENT_TO_ROUTE.get(intent, "respond")


# ---------------------------------------------------------------------------
# Entity extraction (pure Python)
# ---------------------------------------------------------------------------

_MAJOR_ALIASES = {
    "pre-med": "Pre-Med", "premed": "Pre-Med", "pre med": "Pre-Med",
    "medicine": "Pre-Med", "biology": "Biology", "chemistry": "Chemistry",
    "computer science": "Computer Science", "cs": "Computer Science",
    "comp sci": "Computer Science", "software": "Computer Science",
    "engineering": "Engineering", "business": "Business",
    "economics": "Economics", "econ": "Economics", "physics": "Physics",
    "mathematics": "Mathematics", "math": "Mathematics",
    "liberal arts": "Liberal Arts", "undecided": "Undecided",
    "nursing": "Nursing", "nurse": "Nursing", "psychology": "Psychology",
    "psych": "Psychology", "education": "Education", "teaching": "Education",
    "english": "English", "history": "History", "political science": "Political Science",
    "poli sci": "Political Science", "communications": "Communications",
    "journalism": "Journalism", "social work": "Social Work", "art": "Art",
    "sociology": "Sociology", "criminal justice": "Criminal Justice",
    "pre-law": "Pre-Law", "prelaw": "Pre-Law",
}


def _extract_profile(text: str) -> Tuple[Dict[str, Any], str]:
    """Return (profile_updates, human_summary)."""
    t = text.lower()
    updates: Dict[str, Any] = {}

    m = re.search(r"\b([0-4]\.\d{1,2})\b", text)
    if m and float(m.group(1)) <= 4.5:
        updates["gpa"] = float(m.group(1))

    m = re.search(r"\b(1[0-6]\d{2}|[4-9]\d{2})\b", text)
    if m:
        val = int(m.group(1))
        if 400 <= val <= 1600 and str(val) not in ("2024", "2025", "2026"):
            updates["sat_score"] = val

    for alias, canonical in sorted(_MAJOR_ALIASES.items(), key=lambda kv: -len(kv[0])):
        if re.search(rf"\b{re.escape(alias)}\b", t):
            updates["major"] = canonical
            break

    if any(k in t for k in ("first-gen", "first gen", "first generation", "first-generation")):
        updates["is_first_gen"] = True

    if any(k in t for k in ("financial aid", "need aid", "can't afford", "cant afford",
                            "low income", "low-income", "pell")):
        updates["needs_financial_aid"] = True

    m = re.search(r"\b(?:d1|d-1|division\s*1|division\s*i)\s+([a-z]+)", t)
    if m:
        updates["sport"] = m.group(1).capitalize()
        updates["athlete_division"] = "D1"
    elif "recruited athlete" in t or "recruited for" in t:
        updates["athlete_division"] = "D1"

    m = re.search(r"\b(?:i'?m|i am|my name is|this is)\s+([A-Z][a-z]+)\b", text)
    if m and m.group(1).lower() not in _MAJOR_ALIASES:
        updates["name"] = m.group(1)

    summary = ", ".join(f"{k}={v}" for k, v in updates.items())
    return updates, summary


def coordinator_node(state: KindredState) -> Dict[str, Any]:
    """Entry node: run the PRE-GENERATION guardrails, update shared state, and
    choose a route. Safety routing (crisis / distress / high-stakes events /
    out-of-scope) takes precedence over any task intent."""
    text = state["user_input"]
    sid = state.get("session_id", "local")
    prior_messages = state.get("messages", [])
    turn_no = len(prior_messages) // 2 + 1
    updates: Dict[str, Any] = {
        "messages": [{"role": "user", "content": text}],
        "guardrail_flags": [],
    }
    audit_log.log_event(sid, "turn", turn=turn_no, chars=len(text),
                        prior_route=state.get("route"))

    # --- explicit request to speak to a person ---
    if _HUMAN_REQUEST.search(text):
        updates["human_requested"] = True

    # --- hybrid safety classifier (deterministic + one optional LLM opinion) ---
    guard = guardrail_classifier.classify(text, prior_messages)
    distress = guard["distress"]
    sensitive = guard["sensitive"]
    in_scope = guard["in_scope"]
    high_stakes = guardrails.high_stakes_event(text)

    # --- distress handoff: PAUSE state (step 2 & 5 of the protocol) ---
    if state.get("awaiting_resume"):
        if distress in ("", "none") and guardrails.ready_to_resume(text):
            updates["awaiting_resume"] = False
            audit_log.log_event(sid, "distress_resume", turn=turn_no)
            # if the message is only a readiness signal (no real task request),
            # give a soft re-entry; otherwise fall through and handle the request.
            task_intent = classify_intent(text, {**state, "route": "respond"})
            if task_intent == "help":
                updates["intent"] = "resume"
                updates["route"] = "respond"
                return updates
        else:
            updates["intent"] = "emotional_support"
            updates["route"] = "support"
            return updates

    # --- sensitive disclosure: session-only, NOT written to student_profile ---
    if sensitive:
        updates["sensitive_disclosures"] = [
            {"category": c, "snippet": text[:160], "acknowledged": False}
            for c in sensitive
        ]
        audit_log.log_event(sid, "sensitive_disclosure", categories=sensitive)

    # --- profile extraction + contradiction handling ---
    profile_updates, _ = _extract_profile(text)
    pending = list(state.get("profile_conflicts", []))
    conflicts: list = []           # NEW conflicts raised this turn
    stored = dict(state.get("student_profile", {}))
    _confirm_words = ("correct", "yes", "right", "the second", "the lower",
                      "the new", "actually", "i meant", "it's the")

    # (a) resolve any pending conflict the student is now confirming
    if pending:
        still_pending = []
        for c in pending:
            given = profile_updates.get(c["field"])
            confirming = given == c["new"] or (
                given is None and any(w in text.lower() for w in _confirm_words)
            )
            if confirming:
                stored[c["field"]] = c["new"]
                profile_updates.pop(c["field"], None)
                audit_log.log_event(sid, "profile_conflict_resolved", field=c["field"])
            else:
                still_pending.append(c)
        updates["profile_conflicts"] = still_pending
        pending = still_pending

    # (b) apply new profile data; flag material contradictions instead of overwriting
    if profile_updates:
        conflicts = guardrails.profile_contradictions(stored, profile_updates)
        conflicting_fields = {c["field"] for c in conflicts}
        for k, v in profile_updates.items():
            if k not in conflicting_fields:
                stored[k] = v
        if conflicts:
            updates["profile_conflicts"] = pending + conflicts
            audit_log.log_event(sid, "profile_conflict",
                                fields=[c["field"] for c in conflicts])

    updates["student_profile"] = stored

    # --- colleges mentioned ---
    mentioned = college_repo.resolve(text)
    if mentioned:
        discussed = list(state.get("discussed_colleges", []))
        for cid in mentioned:
            if cid not in discussed:
                discussed.append(cid)
        updates["discussed_colleges"] = discussed
        updates["focus_college"] = mentioned[0]
        deadlines = dict(state.get("college_deadlines", {}))
        for cid in mentioned:
            dl = college_repo.deadline_of(cid)
            if dl:
                deadlines[cid] = dl
        updates["college_deadlines"] = deadlines

    # --- ROUTING: safety first, then task intent ---
    if distress == "crisis":
        intent, route = "crisis", "support"
        updates["awaiting_resume"] = True
        audit_log.log_event(sid, "distress_handoff", level="crisis", turn=turn_no)
    elif distress == "distress":
        intent, route = "emotional_support", "support"
        updates["awaiting_resume"] = True
        audit_log.log_event(sid, "distress_handoff", level="distress", turn=turn_no)
    elif high_stakes == "missed_deadline":
        intent, route = "missed_deadline", "support"
        audit_log.log_event(sid, "high_stakes_event", kind="missed_deadline", turn=turn_no)
    elif high_stakes == "scholarship_rejection":
        intent, route = "scholarship_rejection", "support"
        audit_log.log_event(sid, "high_stakes_event", kind="scholarship_rejection", turn=turn_no)
    elif updates.get("human_requested"):
        intent, route = "human_handoff", "respond"
        audit_log.log_event(sid, "human_handoff_requested", turn=turn_no)
    elif not in_scope:
        intent, route = "out_of_scope", "respond"
        audit_log.log_event(sid, "out_of_scope", turn=turn_no)
    elif updates.get("profile_conflicts", state.get("profile_conflicts", [])):
        # don't run a task agent on contradictory profile data - confirm first
        intent, route = "confirm_profile", "respond"
    else:
        intent = classify_intent(text, state)
        route = route_for(intent)
    updates["intent"] = intent
    updates["route"] = route

    # --- ESCALATION (human review criteria) ---
    merged_state = {**state, **updates}
    raised = {e.get("trigger") for e in state.get("escalations", [])}
    esc = guardrails.evaluate_escalation(
        state=merged_state, user_text=text, distress=distress,
        high_stakes=high_stakes, sensitive=sensitive, profile_conflict=conflicts,
    )
    for e in esc:  # audit every occurrence, even repeats
        audit_log.log_event(sid, "escalation", trigger=e.trigger, risk=e.risk, turn=turn_no)
    fresh = [e for e in esc if e.trigger not in raised]
    if fresh:
        updates["escalations"] = [{**e.as_dict(), "turn": turn_no} for e in fresh]

    return updates


_RESUME_MESSAGE = (
    "Thank you for telling me. Take all the time you need - there's no rush on "
    "any of this. When you'd like to pick back up, we can look at colleges, work "
    "on an essay, or map out your deadlines. Where would you like to start?"
)


_HANDOFF_MESSAGE = (
    "Okay - I've flagged this conversation so a Kindred advisor can follow up with "
    "you. They'll have the context of what we've talked about. In the meantime I'm "
    "still here if you want to keep working on anything."
)


def help_node(state: KindredState) -> Dict[str, Any]:
    """Fallback: capabilities menu, scope redirect, re-entry, or handoff confirm."""
    intent = state.get("intent")
    if intent == "out_of_scope":
        return {"response": guardrails.SCOPE_REDIRECT}
    if intent == "resume":
        return {"response": _RESUME_MESSAGE}
    if intent == "human_handoff":
        return {"response": _HANDOFF_MESSAGE}
    if intent == "confirm_profile":
        conflicts = state.get("profile_conflicts", [])[-3:]
        lines = "\n".join(
            f"  • {c['field']}: I have **{c['stored']}** on file, you just said **{c['new']}**"
            for c in conflicts
        )
        return {"response": (
            "I want to make sure I have your information right before I give you "
            f"advice based on it:\n{lines}\n\nWhich is correct? Once you confirm, "
            "I'll update it and we can keep going."
        )}
    msg = (
        "I'm Kindred, your college application guide. I can help you with:\n"
        "  • College discovery  - \"I'm pre-med, 3.2 GPA, D1 soccer. Give me colleges.\"\n"
        "  • College questions   - \"Tell me about Stanford. What's the deadline?\"\n"
        "  • Essay feedback      - \"Here's my Stanford essay draft: ...\"\n"
        "  • Deadline planning   - \"What's my deadline order? Help me plan my weeks.\"\n"
    )
    return {"response": msg}
