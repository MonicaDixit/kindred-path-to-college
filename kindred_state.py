"""
Shared state for the Kindred multi-agent system.

Per the Checkpoint 5 design: a single stateful object that the (deterministic)
Coordinator owns and that every agent reads from / writes to. LangGraph threads
this dict through every node; the Coordinator's checkpointer persists it across
conversational turns so Elena never has to repeat her profile.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, List, TypedDict


class EssayRecord(TypedDict, total=False):
    college: str
    prompt: str
    drafts: List[str]          # draft 1, draft 2, ... (raw student text)
    feedback: List[str]        # agent feedback, one entry per draft
    status: str                # "not_started" | "in_progress" | "complete"


class KindredState(TypedDict, total=False):
    # ---- identity ----
    session_id: str            # thread id, for the audit trail

    # ---- current turn ----
    user_input: str            # raw query from the student this turn
    intent: str                # set by Coordinator.classify_intent
    route: str                 # which agent node to run ("discovery"/"essay"/"planning"/"respond")
    response: str              # formatted answer handed back to the student

    # ---- conversation memory (append-only) ----
    messages: Annotated[List[Dict[str, str]], operator.add]

    # ---- shared student context (owned by Coordinator) ----
    student_profile: Dict[str, Any]      # name, gpa, sat_score, major, is_first_gen, sport, ...
    selected_colleges: List[str]         # college ids the student is targeting
    discussed_colleges: List[str]        # college ids mentioned so far (for "like Stanford, ...")
    college_deadlines: Dict[str, str]    # college id -> ISO application deadline
    focus_college: str                   # college id in focus from the last inquiry

    # ---- domain outputs ----
    essays: Dict[str, EssayRecord]       # college id -> essay record
    timeline: Dict[str, Any]             # Planning agent output (sorted deadlines + weekly plan)
    # Essay Agent methodology state (College Essay Guy path diagnosis). Set once
    # by the Essay Agent from the profile + disclosures; stage is re-derived each
    # essay turn. path: "A".."D"; structure: "narrative"|"montage"; stage:
    # "brainstorm"|"drafting"|"revising".
    essay_path: str
    essay_structure: str
    essay_stage: str

    # ---- Checkpoint 6: safety / guardrails ----
    # Distress handoff protocol: while True the Coordinator suspends the task
    # agents and only the support node runs, until the student signals readiness.
    awaiting_resume: bool
    # Sensitive personal disclosures - session-only, NOT merged into student_profile
    # without explicit acknowledgment. [{category, snippet, acknowledged}]
    sensitive_disclosures: Annotated[List[Dict[str, Any]], operator.add]
    # Unresolved contradictions between this session and the stored profile
    # (replace semantics - the Coordinator clears these once the student confirms).
    profile_conflicts: List[Dict[str, Any]]
    # Human-review escalations raised this conversation. [{trigger, risk, rationale, turn}]
    escalations: Annotated[List[Dict[str, Any]], operator.add]
    # Guardrail flags attached to the most recent response (post-generation checks).
    guardrail_flags: List[str]
    # Whether the student has asked to be connected to a human advisor.
    human_requested: bool


def new_state(student_profile: Dict[str, Any] | None = None,
              session_id: str = "local") -> KindredState:
    """Fresh state for a new student conversation."""
    return KindredState(
        session_id=session_id,
        user_input="",
        intent="",
        route="respond",
        response="",
        messages=[],
        student_profile=student_profile or {},
        selected_colleges=[],
        discussed_colleges=[],
        college_deadlines={},
        focus_college="",
        essays={},
        timeline={},
        essay_path="",
        essay_structure="",
        essay_stage="",
        awaiting_resume=False,
        sensitive_disclosures=[],
        profile_conflicts=[],
        escalations=[],
        guardrail_flags=[],
        human_requested=False,
    )
