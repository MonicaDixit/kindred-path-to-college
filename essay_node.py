"""
Essay Agent node (LLM + RAG examples + coaching methodology).

Checkpoint 5, Agent 2: help students write and revise college essays through
iterative feedback.
  - essay_help     : student pasted a draft -> structured feedback + store revision
  - essay_guidance : student asks how to approach an essay -> strategy + examples

Reads shared state for selected colleges, essay history, and deadlines so
feedback is college-specific and deadline-aware.

Checkpoint 6+: a deterministic path diagnosis (College Essay Guy's A/B/C/D
model) picks a recommended structure and pulls targeted method cards from
essay_methodology.json into the prompt. No extra LLM calls - the diagnosis is
keyword + profile based.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, Dict

import college_repo
import essay_methodology as em
import guardrails
from essay_examples import retrieve_essay_examples
from kindred_state import KindredState
from llm_client import OpenRouterClient

_llm = OpenRouterClient()

_SYSTEM = (
    "You are Kindred's Essay coach for first-generation students. You give "
    "specific, encouraging, actionable feedback - never generic praise. You name "
    "what is working before what needs work. You are given real successful essay "
    "excerpts for reference; use them to illustrate, never tell the student to copy. "
    "You are also given coaching-method notes: use them to guide the student, but "
    "translate them into plain, warm language - never lecture with jargon."
    + guardrails.ESSAY_GUARDRAILS
)

_FEEDBACK_AXES = "authenticity, narrative structure, specificity, and college fit"


def _split_draft(text: str) -> str:
    """Pull the essay body out of 'Here's my Stanford essay: <body>'."""
    for sep in (":", " - ", "\n\n"):
        if sep in text:
            head, _, body = text.partition(sep)
            if len(body.strip()) > 120:
                return body.strip()
    return text.strip()


def _days_to_deadline(state: KindredState, cid: str) -> int | None:
    dl = state.get("college_deadlines", {}).get(cid) or college_repo.deadline_of(cid)
    if not dl:
        return None
    try:
        return (_dt.date.fromisoformat(dl) - _dt.date.today()).days
    except ValueError:
        return None


def _target_college(state: KindredState) -> str:
    return (
        state.get("focus_college")
        or (state.get("selected_colleges") or [""])[0]
        or (state.get("discussed_colleges") or [""])[-1]
    )


def _recent_transcript(state: KindredState, n: int = 6) -> str:
    msgs = state.get("messages", [])[-n:]
    who = {"user": "Student", "assistant": "Kindred"}
    return "\n".join(f"{who.get(m.get('role'), m.get('role'))}: {m.get('content', '')}" for m in msgs)


def _methodology_block(state: KindredState, *, had_draft: bool, draft_count: int) -> Dict[str, Any]:
    """Diagnose path/structure/stage and retrieve targeted method cards.

    Returns {"prompt_text": str, "updates": {...state fields...}, "path": str, ...}.
    """
    profile = state.get("student_profile", {})
    user_text = state.get("user_input", "")
    transcript = _recent_transcript(state) + "\n" + user_text + "\n" + " ".join(
        f"{k}: {v}" for k, v in profile.items()
    )
    disclosures = state.get("sensitive_disclosures", [])

    # path/structure: diagnose once, then keep it stable for the conversation
    path = state.get("essay_path", "")
    structure = state.get("essay_structure", "")
    if not path:
        path, structure = em.diagnose_path(profile, disclosures, transcript)

    stage = em.infer_stage(had_draft, draft_count, user_text)
    prompt_set = em.detect_prompt_set(transcript)

    cards = em.retrieve_methodology(
        path=path, structure=structure, stage=stage, prompt_set=prompt_set,
        query=user_text, k=4,
    )

    guide = (
        f"STUDENT SITUATION (your read, keep it tentative): this student {em.PATH_BLURB.get(path, '')}. "
        f"A {structure} structure tends to fit. They are at the {stage} stage.\n"
        f"If your read of their situation is clearly wrong from what they say, go with what they say.\n\n"
        f"COACHING METHOD NOTES:\n{em.format_cards(cards)}"
    )
    return {
        "prompt_text": guide,
        "updates": {"essay_path": path, "essay_structure": structure, "essay_stage": stage},
        "path": path, "structure": structure, "stage": stage,
    }


def _essay_help(state: KindredState) -> Dict[str, Any]:
    cid = _target_college(state)
    draft = _split_draft(state["user_input"])
    profile = state.get("student_profile", {})

    record = dict(state.get("essays", {}).get(cid, {}))
    drafts = list(record.get("drafts", []))
    drafts.append(draft)
    draft_no = len(drafts)

    method = _methodology_block(state, had_draft=True, draft_count=draft_no)

    examples = retrieve_essay_examples(cid, draft, k=2)
    days = _days_to_deadline(state, cid)
    deadline_note = (
        f"The {college_repo.name_of(cid)} deadline is in {days} days."
        if days is not None else ""
    )

    prompt = (
        f"Student: {profile}\n"
        f"College: {college_repo.name_of(cid) if cid else 'unspecified'}\n"
        f"This is draft #{draft_no}.\n"
        f"{deadline_note}\n\n"
        f"{method['prompt_text']}\n\n"
        f"Reference excerpts from essays that worked:\n{examples}\n\n"
        f"Student's draft:\n\"\"\"\n{draft}\n\"\"\"\n\n"
        f"Give feedback on {_FEEDBACK_AXES}. Start with 2 genuine strengths, then "
        f"3 prioritized revisions with concrete examples of how to fix each. Where "
        f"the draft names an emotion, push the student to show it instead. Make "
        f"sure at least one revision pushes them toward deeper reflection - the "
        f"'so what' the reader should take away. End with one sentence on what to "
        f"focus on for draft #{draft_no + 1}."
        + (f" Note the deadline: {deadline_note}" if deadline_note else "")
    )
    feedback = _llm.call([{"role": "user", "content": prompt}], _SYSTEM)

    feedbacks = list(record.get("feedback", []))
    feedbacks.append(feedback)
    essays = dict(state.get("essays", {}))
    essays[cid] = {
        "college": cid,
        "prompt": record.get("prompt", ""),
        "drafts": drafts,
        "feedback": feedbacks,
        "status": "in_progress",
    }
    return {
        "response": feedback,
        "essays": essays,
        "focus_college": cid,
        **method["updates"],
    }


def _essay_guidance(state: KindredState) -> Dict[str, Any]:
    cid = _target_college(state)
    profile = state.get("student_profile", {})
    examples = retrieve_essay_examples(cid, state["user_input"], k=2)
    days = _days_to_deadline(state, cid) if cid else None
    rec = state.get("essays", {}).get(cid, {})
    follow_up = state.get("intent") == "essay_followup"

    method = _methodology_block(
        state, had_draft=False, draft_count=len(rec.get("drafts", [])),
    )

    prompt = (
        f"Student: {profile}\n"
        f"College: {college_repo.name_of(cid) if cid else 'general / Common App'}\n"
        + (f"Deadline in {days} days.\n" if days is not None else "")
        + (f"Drafts so far for this college: {len(rec.get('drafts', []))}.\n" if rec else "")
        + f"\n{method['prompt_text']}\n"
        + f"\nRecent conversation:\n{_recent_transcript(state)}\n\n"
        + f"Student now asks: {state['user_input']!r}\n\n"
        f"Reference excerpts from essays that worked:\n{examples}\n\n"
        + (
            "Answer their follow-up question directly and conversationally, "
            "building on the conversation above. Be concrete and encouraging, and "
            "keep the coaching method above in mind."
            if follow_up else
            "Give concrete guidance on how to approach this essay: name the "
            "structure that fits and why, 2-3 possible angles rooted in THIS "
            "student's background and what this college values, and one "
            "brainstorming exercise to do today (draw it from the method notes). "
            "Reference an excerpt to show, not tell."
        )
    )
    answer = _llm.call([{"role": "user", "content": prompt}], _SYSTEM)
    return {
        "response": answer,
        "focus_college": cid or state.get("focus_college", ""),
        **method["updates"],
    }


def essay_node(state: KindredState) -> Dict[str, Any]:
    if state.get("intent") == "essay_help":
        return _essay_help(state)
    return _essay_guidance(state)
