"""
Defense-in-depth guardrails for Kindred (Capstone Checkpoint 6).

Three pipeline layers plus two whole-person layers:

  PRE-GENERATION   validate_profile / scope_check / distress_signal /
                   high_stakes_event / detect_sensitive_disclosure /
                   profile_contradictions
  DURING           DISCOVERY_GUARDRAILS / ESSAY_GUARDRAILS  (system-prompt text)
  POST-GENERATION  check_confidence_calibration / validate_discovery_output /
                   validate_planning_output / validate_essay_output
  VULNERABILITY    detect_sensitive_disclosure (+ "session-only, no auto-persist"
                   handled in the Coordinator) and the distress handoff
  ESCALATION       evaluate_escalation  -> human review queue (audit_log)

Classifiers are HYBRID: distress / crisis are deterministic here (fast, safety
critical); scope + sensitive-disclosure get a second LLM opinion in
`guardrail_classifier.py`, which falls back to the deterministic checks here.
"""

from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import college_repo

# ===========================================================================
# Constants
# ===========================================================================

# Fields the Discovery Agent needs before it can responsibly recommend.
PROFILE_REQUIRED_FOR_RECS = ("gpa", "major")
# Fields that materially affect recommendation quality - used for the
# "missing > 2 required fields" escalation (doc: underpopulated profile).
PROFILE_TRACKED_FIELDS = (
    "gpa", "sat_score", "major", "is_first_gen", "needs_financial_aid",
)

# --- distress / crisis (deterministic, checked before any task routing) ---
CRISIS_KW = (
    "kill myself", "killing myself", "end my life", "end it all", "want to die",
    "wanna die", "don't want to live", "dont want to live", "no reason to live",
    "not worth living", "better off dead", "better off without me",
    "hurt myself", "harm myself", "harming myself", "suicidal", "suicide",
    "self harm", "self-harm", "cut myself", "don't want to be here anymore",
    "dont want to be here anymore", "don't want to be alive", "dont want to be alive",
)
DISTRESS_KW = (
    "overwhelmed", "so overwhelmed", "can't do this", "cant do this",
    "can't handle", "cant handle", "too much for me", "waste of time",
    "pointless", "no point", "don't see a point", "dont see a point",
    "don't see the point", "dont see the point", "what's the point",
    "whats the point", "give up", "giving up", "want to quit", "wanna quit",
    "want to give up", "hopeless", "no hope", "never getting in",
    "never get into college", "never getting into college", "not smart enough",
    "not good enough", "i'm a failure", "im a failure", "i am a failure",
    "such a failure", "end up on the street", "end up on the streets",
    "end up homeless", "no one to guide me", "no one to help me",
    "nobody to help me", "no one is helping me", "breaking down",
    "falling apart", "burnt out", "burned out", "i can't keep going",
    "i cant keep going", "no point in continuing", "spiraling", "panic attack",
    "crying", "can't stop crying", "cant stop crying",
)

# --- high-stakes emotionally significant events (regex - phrasing varies a lot) ---
MISSED_DEADLINE_RE = re.compile(
    r"(miss(?:ed|ing)?\s+(?:the\s+|my\s+|a\s+|\w+\s+){0,3}(?:deadline|application|"
    r"cutoff)"
    r"|(?:deadline|application)\s+(?:has\s+)?(?:already\s+)?(?:passed|closed)"
    r"|too late to (?:apply|submit)"
    r"|didn'?t\s+(?:submit|get it in|finish)\s+(?:in time|before the deadline)"
    r"|forgot to submit)",
    re.I,
)
SCHOLARSHIP_REJECTION_RE = re.compile(
    r"(didn'?t\s+(?:get|win|receive)\s+(?:the\s+|my\s+|a\s+)?(?:scholarship|grant|"
    r"award|funding)"
    r"|(?:scholarship|grant|funding|award)\s+(?:was\s+|got\s+|(?:has\s+)?been\s+)?"
    r"(?:rejected|denied|declined|turned down)"
    r"|(?:rejected|denied|declined|turned down)\s+for\s+(?:the\s+|a\s+|my\s+)?"
    r"(?:scholarship|grant)"
    r"|(?:got|was)\s+denied\s+(?:the\s+|a\s+|my\s+)?(?:scholarship|grant|funding)"
    r"|lost\s+(?:my\s+|the\s+)?(?:scholarship|funding|grant)"
    r"|scholarship\s+fell\s+through"
    r"|didn'?t\s+(?:get|receive)\s+(?:any\s+)?funding)",
    re.I,
)

# --- coding / homework / creative-writing-for-me - out of scope ---
CODE_RE = re.compile(
    r"\b(write (?:me |my |the |some |a )*(?:code|program|function|script|python|java|"
    r"javascript|c\+\+|poem|story|song|joke|rap|screenplay|essay about (?!college|"
    r"why|my))"
    r"|debug (?:this|my)|fix (?:this|my) (?:code|bug)|linked list|binary tree|"
    r"for loop|def \w+\(|import \w+|leetcode|my homework|solve this (?:problem|equation)"
    r"|do my assignment|roleplay|role-play|pretend (?:to be|you are|you're))\b",
    re.I,
)

# --- student signals they are ready to continue after a distress pause ---
READY_KW = (
    "i'm ok", "im ok", "i'm okay", "im okay", "i'm good now", "im good now",
    "let's continue", "lets continue", "let's keep going", "lets keep going",
    "i'm ready", "im ready", "keep going", "we can continue", "let's move on",
    "lets move on", "i want to continue", "back to", "let's get back",
    "thanks, i'm better", "feeling better", "ready to keep going",
)

# --- financial-aid / scholarship-eligibility queries -> High escalation ---
FINANCIAL_QUERY_KW = (
    "how much aid", "how much financial aid", "how much will i get",
    "am i eligible for", "will i qualify for", "scholarship eligibility",
    "how much money", "expected family contribution", "efc", "sai",
    "how much can i borrow", "loan amount", "grant amount", "how much is the",
    "net price", "net cost", "what will i pay", "how much do i pay",
    "what will it cost me", "can i afford", "cost for me", "my award",
)

# --- topic scope: things Kindred is NOT for ---
OUT_OF_SCOPE_KW = (
    "write my code", "debug this", "homework answer", "do my homework",
    "medical advice", "diagnose", "prescription", "legal advice", "sue",
    "immigration lawyer", "tax return", "stock", "crypto", "invest in",
    "recipe", "who won", "sports score", "movie recommendation",
    "write a poem about", "roleplay", "pretend you are", "jailbreak",
    "ignore your instructions", "ignore previous instructions",
    "system prompt",
)
IN_SCOPE_HINT_KW = (
    "college", "university", "school", "essay", "personal statement", "application",
    "deadline", "scholarship", "financial aid", "fafsa", "css profile", "major",
    "gpa", "sat", "act", "admission", "reach", "target", "safety", "recommend",
    "first-gen", "first generation", "counselor", "transcript", "extracurricular",
    "waitlist", "early decision", "early action", "common app", "coalition",
)

# --- post-generation: overconfident / uncalibrated language ---
# Deliberately narrow: words like "always"/"never"/"impossible" are usually used
# in HONEST hedging ("there's never a guarantee") so they are not included.
OVERCONFIDENT_PATTERNS = (
    r"\bdefinitely (?:get|be admitted|be accepted|get in)\b",
    r"\bguaranteed\b", r"\bi guarantee\b", r"\b100% (?:chance|sure|certain)\b",
    r"\byou will (?:get in|be admitted|get accepted|be accepted)\b",
    r"\byou'll (?:get in|be admitted|get accepted|be accepted)\b",
    r"\byou're (?:definitely|certainly) getting in\b",
    r"\bthere's no way you (?:won't|wont) (?:get in|be admitted)\b",
    r"\beveryone (?:who applies )?gets in\b",
    r"\bslam dunk\b", r"\bsure thing\b", r"\ba lock\b",
)
TIME_SENSITIVE_TERMS = (
    "deadline", "due date", "acceptance rate", "admit rate", "admission rate",
    "scholarship", "tuition", "cost of attendance", "financial aid", "award",
    "requirement", "test-optional", "test optional", "sat range", "gpa range",
)

# --- sensitive personal disclosure categories (deterministic seed) ---
SENSITIVE_CATEGORIES: Dict[str, tuple] = {
    "immigration_status": (
        "undocumented", "daca", "dreamer", "no papers", "no green card",
        "asylum", "refugee", "tps", "without status", "immigration status",
        "my visa", "overstayed",
    ),
    "family_trauma": (
        "my parent died", "passed away", "my mom died", "my dad died",
        "abusive", "abuse", "domestic violence", "foster care", "group home",
        "incarcerated", "in prison", "in jail", "deported", "divorce was",
        "kicked me out", "homeless", "we were evicted", "shelter",
    ),
    "financial_hardship": (
        "we can't afford", "we cant afford", "we have no money", "on food stamps",
        "snap benefits", "we're broke", "were broke", "poverty", "evicted",
        "can't pay rent", "cant pay rent", "working two jobs", "working full time",
        "support my family", "no money for",
    ),
    "mental_health": (
        "depression", "depressed", "anxiety disorder", "panic attacks",
        "therapy", "therapist", "psychiatrist", "medication for", "self-harm",
        "eating disorder", "hospitalized", "mental health", "ptsd", "trauma",
        "adhd", "on antidepressants",
    ),
    "safety": (
        "unsafe at home", "not safe at home", "afraid of my", "someone hurt me",
        "being hurt", "assault", "assaulted", "harassed", "stalker",
    ),
}


# ===========================================================================
# PRE-GENERATION
# ===========================================================================

@dataclass
class ProfileValidation:
    ok_for_recs: bool
    missing_required: List[str]
    missing_tracked: List[str]


def validate_profile(profile: Dict[str, Any]) -> ProfileValidation:
    missing_req = [f for f in PROFILE_REQUIRED_FOR_RECS if not profile.get(f)]
    missing_all = [f for f in PROFILE_TRACKED_FIELDS if not profile.get(f)]
    return ProfileValidation(
        ok_for_recs=not missing_req,
        missing_required=missing_req,
        missing_tracked=missing_all,
    )


SCOPE_REDIRECT = (
    "I'm Kindred - I help first-generation students with college discovery, "
    "essays, financial aid, and application deadlines. That's a bit outside what "
    "I can help with, but if any part of your college search is on your mind, "
    "I'm here for that."
)


def scope_check(text: str) -> bool:
    """Deterministic base scope check. Returns True if in-scope.
    `guardrail_classifier.classify` may override with an LLM opinion."""
    t = text.lower()
    if any(k in t for k in OUT_OF_SCOPE_KW) or CODE_RE.search(text):
        return False
    # short greetings / meta are fine
    if len(t.split()) <= 4:
        return True
    # if it clearly mentions the domain, in-scope
    if any(k in t for k in IN_SCOPE_HINT_KW):
        return True
    # otherwise: neutral -> let it through (the agents handle "I don't know")
    return True


def high_stakes_event(text: str) -> str:
    """Return 'missed_deadline', 'scholarship_rejection', or ''."""
    if SCHOLARSHIP_REJECTION_RE.search(text):
        return "scholarship_rejection"
    if MISSED_DEADLINE_RE.search(text):
        return "missed_deadline"
    return ""


def distress_signal(text: str, recent_messages: Optional[List[Dict[str, str]]] = None) -> str:
    """Return 'crisis', 'distress', or ''. Deterministic + a cross-turn
    escalation check (negative sentiment persisting after a support turn)."""
    t = text.lower()
    if any(k in t for k in CRISIS_KW):
        return "crisis"
    if any(k in t for k in DISTRESS_KW):
        return "distress"
    # escalation across consecutive turns: the last assistant turn was a support
    # message and the student is still negative / short-and-flat
    if recent_messages:
        last_assistant = next(
            (m for m in reversed(recent_messages) if m.get("role") == "assistant"), None
        )
        if last_assistant and "988" in last_assistant.get("content", ""):
            neg = ("i can't", "i cant", "still", "nothing helps", "whatever",
                   "doesn't matter", "doesnt matter", "no", "idk", "i don't know")
            if any(t.strip().startswith(n) or t.strip() == n for n in neg):
                return "distress"
    return ""


def ready_to_resume(text: str) -> bool:
    t = text.lower().strip()
    return any(k in t for k in READY_KW)


def is_financial_query(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in FINANCIAL_QUERY_KW)


def detect_sensitive_disclosure(text: str) -> List[str]:
    """Deterministic base. Returns the list of sensitive categories present."""
    t = text.lower()
    hits = []
    for category, kws in SENSITIVE_CATEGORIES.items():
        if any(k in t for k in kws):
            hits.append(category)
    return hits


def profile_contradictions(current: Dict[str, Any], incoming: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Compare new profile data against what's stored. Returns material conflicts
    (not just refinements). The Coordinator does NOT silently overwrite these."""
    conflicts = []
    for field, new_val in incoming.items():
        old_val = current.get(field)
        if old_val is None or old_val == new_val:
            continue
        material = False
        if field == "gpa":
            try:
                material = abs(float(old_val) - float(new_val)) >= 0.3
            except (TypeError, ValueError):
                material = True
        elif field == "sat_score":
            try:
                material = abs(int(old_val) - int(new_val)) >= 100
            except (TypeError, ValueError):
                material = True
        elif field in ("major", "state", "grade_level"):
            material = str(old_val).lower() != str(new_val).lower()
        elif field in ("is_first_gen", "needs_financial_aid"):
            material = bool(old_val) != bool(new_val)
        if material:
            conflicts.append({"field": field, "stored": old_val, "new": new_val})
    return conflicts


# ===========================================================================
# DURING - system-prompt guardrail text (appended to each agent's prompt)
# ===========================================================================

DISCOVERY_GUARDRAILS = (
    "\n\nGUARDRAILS (follow exactly):\n"
    "- Only name colleges that appear in the structured data you are given. Never "
    "introduce a college that is not in that data.\n"
    "- Attribute factual claims (acceptance rate, deadline, cost, aid policy) to "
    "the provided data. If a figure is not in the data, say you don't have it and "
    "suggest the student verify on the college's website - do not estimate.\n"
    "- Never express certainty about admission. No 'you will get in', 'guaranteed', "
    "'definitely', 'for sure'. Use calibrated language: 'likely', 'a realistic "
    "target', 'a reach'.\n"
    "- EQUITY CONSISTENCY: your reach/target/safety categorization and fit "
    "assessment must be based ONLY on the computed academic/statistical data. Do "
    "NOT soften a 'reach' to a 'target', inflate chances, or change any "
    "recommendation because the student's personal circumstances are sympathetic. "
    "A student facing real hardship deserves honest guidance, not wishful "
    "guidance.\n"
    "- Do not repeat back sensitive personal details the student shared. You may "
    "note a strong personal narrative as a potential essay strength, briefly."
)

ESSAY_GUARDRAILS = (
    "\n\nGUARDRAILS (follow exactly):\n"
    "- PRESERVE STUDENT AUTHORSHIP. Give questions, observations, and structural "
    "suggestions. Do NOT write full replacement paragraphs or sentences in the "
    "student's voice. If you show phrasing, keep it to a short fragment clearly "
    "marked as an example the student should rewrite in their own words.\n"
    "- VOICE: prioritise the student's concrete, specific detail over 'impressive' "
    "or formal language. An authentic voice that doesn't sound like a prep-school "
    "essay is an asset, not a flaw to correct.\n"
    "- HONESTY: every time you evaluate a draft, include at least one specific, "
    "actionable thing to improve. Never give uniformly positive feedback.\n"
    "- NO FABRICATION: do not invent biographical facts about the student. If no "
    "draft was submitted, do not write first-person narrative as if it were "
    "theirs. Use only clearly-labelled external/anonymised illustrations.\n"
    "- COLLEGE CLAIMS: base any claim about a college's values or what it looks "
    "for on the provided data. Hedge unsourced claims.\n"
    "- REFERENCE EXAMPLES are for structure only - never present them as a "
    "template to copy.\n"
    "- SENSITIVE MATERIAL: if the draft covers trauma, immigration, family "
    "hardship, or mental health, do not echo the details back clinically or "
    "reductively. Focus feedback on craft and structure, and treat what they "
    "shared with respect."
)


# ===========================================================================
# POST-GENERATION
# ===========================================================================

@dataclass
class Issue:
    code: str          # machine slug, e.g. "hallucinated_college"
    severity: str      # "block" | "hedge" | "flag"
    detail: str


def check_confidence_calibration(text: str) -> List[str]:
    """Return overconfident phrases that appear near time-sensitive terms
    (or admission-outcome claims)."""
    t = text.lower()
    flagged = []
    for pat in OVERCONFIDENT_PATTERNS:
        for m in re.finditer(pat, t):
            window = t[max(0, m.start() - 120): m.end() + 120]
            if ("admit" in window or "get in" in window or "accepted" in window
                    or any(term in window for term in TIME_SENSITIVE_TERMS)):
                flagged.append(m.group(0))
    return sorted(set(flagged))


def validate_discovery_output(text: str, allowed_college_names: List[str]) -> List[Issue]:
    issues: List[Issue] = []
    allowed = {n.lower() for n in allowed_college_names}
    # college names the model introduced that aren't in the allowed set
    mentioned = college_repo.resolve(text)
    known = {college_repo.name_of(cid).lower() for cid in mentioned}
    # also catch "University of X" / "X University" / "X College" strings
    for m in re.finditer(r"\b([A-Z][A-Za-z.&'\-]+(?:\s+[A-Z][A-Za-z.&'\-]+){0,4}\s+(?:University|College|Institute of Technology|State))\b", text):
        known.add(m.group(1).lower())
    for m in re.finditer(r"\bUniversity of ([A-Z][A-Za-z.&'\-]+(?:\s+[A-Z][A-Za-z.&'\-]+){0,3})\b", text):
        known.add(("university of " + m.group(1)).lower())
    strangers = sorted(n for n in known if n and n not in allowed
                       and not any(a in n or n in a for a in allowed))
    if strangers:
        issues.append(Issue(
            "hallucinated_college", "hedge",
            f"names not in the provided data: {', '.join(strangers[:5])}",
        ))
    conf = check_confidence_calibration(text)
    if conf:
        issues.append(Issue(
            "overconfident_claim", "hedge",
            f"uncalibrated language: {', '.join(conf)}",
        ))
    return issues


def validate_planning_output(timeline: Dict[str, Any]) -> List[Issue]:
    issues: List[Issue] = []
    if not timeline or timeline.get("error"):
        return issues
    rows = timeline.get("deadline_order", [])
    today = _dt.date.today()
    # 1. ordering: days_left ascending
    dl = [r.get("days_left") for r in rows if isinstance(r.get("days_left"), int)]
    if dl != sorted(dl):
        issues.append(Issue("deadline_out_of_order", "block", "deadline_order not sorted by urgency"))
    for r in rows:
        d = r.get("deadline")
        try:
            parsed = _dt.date.fromisoformat(d)
        except (TypeError, ValueError):
            issues.append(Issue("bad_deadline_date", "block", f"unparseable deadline: {d!r}"))
            continue
        # 2. arithmetic: stored days_left matches recomputed
        if isinstance(r.get("days_left"), int):
            recomputed = (parsed - today).days
            if abs(recomputed - r["days_left"]) > 1:
                issues.append(Issue(
                    "deadline_arithmetic", "block",
                    f"{r.get('college')}: days_left {r['days_left']} != {recomputed}",
                ))
        # 3. future-dated
        if parsed < today:
            issues.append(Issue(
                "past_deadline", "flag",
                f"{r.get('college')} deadline {d} is in the past",
            ))
    return issues


_QUESTION_OR_SUGGESTION = re.compile(
    r"(\?|consider|could you|what if|try|you might|i'd suggest|think about|"
    r"one option|for example|maybe|how about|instead of)", re.I,
)
_IMPROVEMENT_MARKERS = re.compile(
    r"(revise|revision|improve|strengthen|tighten|cut|expand|unclear|vague|"
    r"needs?\s|weak|could be|missing|instead|rework|reconsider|too general|"
    r"show(?:,| ) don't tell|specific(?:ity)?|next draft|work on)", re.I,
)
_FIRST_PERSON_BIO = re.compile(
    r"\b(I (?:was born|grew up|immigrated|remember when|am the (?:first|oldest|youngest))|"
    r"my (?:mother|father|mom|dad|family) (?:worked|immigrated|struggled|told me))\b", re.I,
)

# post-gen (methodology): essay feedback that never pushes the student toward
# meaning / the "so what". Deliberately broad - only genuinely shallow feedback
# (all praise + surface fixes, no reflection) should trip it.
_REFLECTION_PROMPT = re.compile(
    r"(so what|why (?:it|this|that) matter|what (?:it|this|that) (?:means?|meant|"
    r"taught|reveal|says? about)|reflect|reflection|insight|takeaway|what you "
    r"learned|dig deeper|go deeper|deeper meaning|the meaning|realiz|what this "
    r"shows about you|why you care|what changed in you|bigger picture)", re.I,
)
# essay feedback (early stages) that never talks about how the piece is built.
# Kept to markers that mean deliberate shaping - not generic "fix this paragraph".
_STRUCTURE_GUIDANCE = re.compile(
    r"(struct|narrativ|montage|chronolog|focusing lens|framing device|"
    r"the order|order of|reorder|sequence of|arc of the|story beat|"
    r"how (?:it|the essay) (?:is|'?s) (?:built|organi[sz]ed|put together)|"
    r"flow of the essay|open on|start with the scene|build tension)", re.I,
)


def validate_essay_output(text: str, had_draft: bool, draft_text: Optional[str],
                          *, stage: str = "", essay_path: str = "") -> List[Issue]:
    issues: List[Issue] = []
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

    # M1. no reflection push: feedback that never steers toward the "so what".
    #     Applies to any draft review, and to brainstorm/drafting guidance.
    if (had_draft or stage in ("brainstorm", "drafting")) and not _REFLECTION_PROMPT.search(text):
        issues.append(Issue("no_reflection_prompt", "regenerate",
                            "essay feedback never pushes the student toward meaning / the 'so what'"))

    # M2. no structure guidance while the essay is still being shaped.
    if (essay_path and stage in ("brainstorm", "drafting")
            and not _STRUCTURE_GUIDANCE.search(text)):
        issues.append(Issue("missing_structure_guidance", "regenerate",
                            "early-stage essay guidance with no advice on how the piece is built"))

    # 1. sycophancy: a draft evaluation with no actionable improvement
    if had_draft and not _IMPROVEMENT_MARKERS.search(text):
        issues.append(Issue("sycophancy", "regenerate",
                            "draft feedback with no specific area to improve"))

    # 2. anti-ghostwriting: (a) an explicit "here's a rewrite" offer, or (b) a
    #    long paragraph of FIRST-PERSON NARRATIVE prose (not feedback about the
    #    draft) that reuses the draft's material.
    ghost = False
    if re.search(r"\b(here(?:'s| is) (?:a |my |the )?(?:rewrite|rewritten|revised version)"
                 r"|rewritten version|try this version|here'?s how i'?d write it"
                 r"|revised (?:paragraph|version) below|let me rewrite)\b", text, re.I):
        ghost = True

    _feedback_lang = re.compile(
        r"\b(your draft|you wrote|this line|that line|the sentence|your opening|"
        r"your hook|the opening|the hook|the phrase|you say|you're saying|"
        r"this paragraph|as written|the draft|consider|suggest|instead of|"
        r"what if you|you could|you might|it reads|this works|cliche|specificity)\b",
        re.I)
    _first_person_narr = re.compile(
        r"\bI\s+(?:went|saw|felt|reali[sz]ed|remember|walked|stood|knew|was|watched|"
        r"heard|ran|opened|found|learned|understood|decided|started)\b"
        r"|\bmy\s+(?:mother|father|mom|dad|family|hands|heart|grandmother|"
        r"grandfather|coach|teacher)\s+\w+ed\b", re.I)
    # a paragraph that quotes and attributes an outside example is illustration,
    # not ghostwriting - the Essay Agent is told to reference example excerpts.
    _example_marker = re.compile(
        r"\b(excerpt|another student|a different student|the writer|a past student|"
        r"one student's|from an essay that worked|for example[,:]|e\.g\.|"
        r"sample (?:essay|line|opening)|reference essay)\b", re.I)
    draft_words = set(re.findall(r"[a-z']+", (draft_text or "").lower()))
    for p in paras:
        wc = len(p.split())
        if wc < 55 or _QUESTION_OR_SUGGESTION.search(p) or _feedback_lang.search(p):
            continue
        if _example_marker.search(p):
            continue
        if p.lstrip().startswith(("-", "*", "1.", "2.", "3.", "4.", "#", ">")):
            continue
        if not _first_person_narr.search(p):
            continue
        pw = set(re.findall(r"[a-z']+", p.lower()))
        overlap = len(pw & draft_words) / max(1, len(pw))
        if not draft_text or overlap > 0.28:
            ghost = True
            break
    if ghost:
        issues.append(Issue("ghostwriting", "hedge", "substitute prose in the student's voice"))

    # 3. fabrication: first-person biographical narrative when no draft was given
    if not had_draft and _FIRST_PERSON_BIO.search(text):
        issues.append(Issue("fabricated_biography", "hedge",
                            "first-person biographical prose with no submitted draft"))

    conf = check_confidence_calibration(text)
    if conf:
        issues.append(Issue("overconfident_claim", "hedge",
                            f"uncalibrated language: {', '.join(conf)}"))
    return issues


# ===========================================================================
# ESCALATION  (Checkpoint 6 "Human Intervention Criteria")
# ===========================================================================

@dataclass
class Escalation:
    trigger: str
    risk: str        # "High" | "Medium"
    rationale: str

    def as_dict(self) -> Dict[str, str]:
        return {"trigger": self.trigger, "risk": self.risk, "rationale": self.rationale}


def evaluate_escalation(
    *,
    state: Dict[str, Any],
    user_text: str,
    distress: str,
    high_stakes: str,
    sensitive: List[str],
    profile_conflict: List[Dict[str, Any]],
    post_gen_issues: Optional[List[Issue]] = None,
    already_raised: Optional[set] = None,
) -> List[Escalation]:
    esc: List[Escalation] = []
    post_gen_issues = post_gen_issues or []
    already_raised = already_raised or set()

    if distress == "crisis":
        esc.append(Escalation("crisis_language", "High",
                              "Self-harm / suicidal language. Autonomous advising paused; crisis resources given."))
    elif distress == "distress":
        esc.append(Escalation("student_distress", "High",
                              "Student expressed overwhelm / hopelessness. 5-step handoff protocol engaged."))

    if high_stakes == "missed_deadline":
        esc.append(Escalation("missed_deadline", "High",
                              "High-stakes event with potential distress. Distress check runs before alternatives."))
    elif high_stakes == "scholarship_rejection":
        esc.append(Escalation("scholarship_rejection", "High",
                              "Financial loss that may affect ability to attend. Human handoff offered."))

    if is_financial_query(user_text):
        esc.append(Escalation("financial_aid_query", "High",
                              "Financial guidance is high-stakes; errors directly harm access decisions."))

    if profile_conflict:
        fields = ", ".join(c["field"] for c in profile_conflict)
        esc.append(Escalation("profile_contradiction", "Medium",
                              f"Session data contradicts stored profile ({fields}); human review resolves ground truth."))

    missing = validate_profile(state.get("student_profile", {})).missing_tracked
    if len(missing) > 2 and state.get("route") == "discovery":
        esc.append(Escalation("underpopulated_profile", "Medium",
                              f"Profile missing >2 fields ({', '.join(missing)}); recommendations may be disconnected."))

    overconf = [i for i in post_gen_issues if i.code == "overconfident_claim"]
    halluc = [i for i in post_gen_issues if i.code == "hallucinated_college"]
    if len(overconf) + len(halluc) >= 1 and (len(overconf) > 1 or halluc):
        esc.append(Escalation("discovery_confidence_failures", "High",
                              "Multiple confidence / grounding failures suggest retrieval breakdown."))

    if sensitive:
        esc.append(Escalation("sensitive_disclosure", "Medium",
                              f"Sensitive disclosure ({', '.join(sensitive)}). Session-only; handoff offered if distress present."))

    if state.get("human_requested"):
        esc.append(Escalation("human_requested", "High",
                              "Student explicitly asked to speak with a person."))

    # de-dupe by trigger, and drop anything already raised this conversation
    seen, out = set(already_raised), []
    for e in esc:
        if e.trigger not in seen:
            seen.add(e.trigger)
            out.append(e)
    return out


# --- triggers that are surfaced to the reviewer but NOT via a task-route banner ---
_NON_BANNER_TRIGGERS = ("student_distress", "crisis_language")


def high_escalations_this_turn(
    escalations: List[Dict[str, Any]],
    turn: int,
    user_text: str = "",
) -> List[Dict[str, Any]]:
    """High-risk escalations attributable to `turn`.

    `escalations` accumulates for the whole conversation (audit trail), each entry
    tagged with the `turn` it was raised on. The student-facing "flagged for a
    human" banner / notice must only reflect the CURRENT turn - otherwise an
    earlier turn's High escalation (e.g. a discovery hallucination) keeps
    re-flagging every later essay / discovery answer.

    A direct financial query is the exception: it re-flags every time it is asked,
    even though the Coordinator de-dupes the trigger out of the accumulating list.
    """
    hits = [
        e for e in escalations
        if e.get("turn") == turn
        and e.get("risk") == "High"
        and e.get("trigger") not in _NON_BANNER_TRIGGERS
    ]
    if (
        user_text
        and is_financial_query(user_text)
        and not any(e.get("trigger") == "financial_aid_query" for e in hits)
    ):
        hits = hits + [
            {"trigger": "financial_aid_query", "risk": "High", "turn": turn}
        ]
    return hits


HEDGE_NOTE = (
    "\n\n_A note on the above: some of this may be time-sensitive or not fully "
    "verified. Please confirm any deadline, cost, or aid figure on the college's "
    "official website before you rely on it._"
)

ESCALATION_NOTICE = (
    "\n\n---\n**Kindred has flagged this for a human advisor to review.** What I've "
    "shared may still help in the meantime, but a person will take a look. If you'd "
    "like to talk to someone directly, just say \"connect me with an advisor.\""
)
