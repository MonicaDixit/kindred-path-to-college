"""
Post-generation validation node (Checkpoint 6).

Every agent (support / discovery / essay / planning / respond) sets `response`
but does NOT append the assistant turn to `messages`. This node runs last:

  1. schema / calibration / authorship checks on the agent's output
  2. hedge or regenerate on failure
  3. raise post-generation escalations
  4. append the (possibly modified) assistant turn to `messages`
  5. log everything to the audit trail

Support-route responses are hand-written and pass through untouched (they still
get logged); the hedging / escalation-notice machinery would only make a crisis
or support reply feel colder.
"""

from __future__ import annotations

from typing import Any, Dict, List

import audit_log
import college_repo
import guardrails
from essay_node import _target_college  # reuse the same target-college logic
from kindred_state import KindredState
from llm_client import OpenRouterClient

_llm = OpenRouterClient()

_ALL_COLLEGE_NAMES = [college_repo.name_of(cid) for cid in college_repo.all_ids()]


_RETRY_FIX = {
    "sycophancy": ("was too uniformly positive - include at least two specific, "
                   "actionable things to improve, each tied to a concrete moment"),
    "no_reflection_prompt": ("never pushed the student to dig into meaning - add a "
                             "prompt that makes them answer 'so what?': what the "
                             "reader should understand about them because of this"),
    "missing_structure_guidance": ("didn't say anything about how to build the "
                                   "piece - name a structure (a single story / a "
                                   "montage under one lens) and why it fits, and "
                                   "one concrete note on ordering or scene"),
}


def _regenerate_essay(state: KindredState, issues: list) -> str:
    """One targeted retry when the essay response failed a methodology check."""
    codes = [i.code for i in issues if i.severity == "regenerate"]
    fixes = [f"- Your previous answer {_RETRY_FIX[c]}." for c in codes if c in _RETRY_FIX]
    if not fixes:
        fixes = [f"- Your previous answer {_RETRY_FIX['sycophancy']}."]
    prompt = (
        "Re-give your essay feedback. Keep the warmth and the strengths you named, "
        "but fix these problems:\n" + "\n".join(fixes) + "\n\n"
        f"The student asked: {state.get('user_input', '')!r}"
    )
    try:
        return _llm.call([{"role": "user", "content": prompt}],
                         "You are Kindred's Essay coach. Balanced, specific, kind.")
    except Exception:  # noqa: BLE001
        return ""


def validate_node(state: KindredState) -> Dict[str, Any]:
    sid = state.get("session_id", "local")
    route = state.get("route", "respond")
    intent = state.get("intent", "")
    text = state.get("response", "") or ""
    issues: List[guardrails.Issue] = []

    # ---- run the layer-appropriate validator ----
    if route == "discovery":
        issues = guardrails.validate_discovery_output(text, _ALL_COLLEGE_NAMES)
    elif route == "planning":
        issues = guardrails.validate_planning_output(state.get("timeline", {}))
    elif route == "essay":
        had_draft = intent == "essay_help"
        draft = None
        if had_draft:
            cid = _target_college(state)
            rec = state.get("essays", {}).get(cid, {})
            draft = (rec.get("drafts") or [None])[-1]
        e_stage = state.get("essay_stage", "")
        e_path = state.get("essay_path", "")
        issues = guardrails.validate_essay_output(
            text, had_draft, draft, stage=e_stage, essay_path=e_path
        )

    flags = sorted({i.code for i in issues})

    # ---- act on the issues ----
    final = text
    if route != "support":
        if any(i.severity == "regenerate" for i in issues):
            retry = _regenerate_essay(state, issues)
            if retry:
                final = retry
                issues = guardrails.validate_essay_output(
                    final, intent == "essay_help",
                    draft if intent == "essay_help" else None,
                    stage=state.get("essay_stage", ""), essay_path=state.get("essay_path", ""),
                )
                flags = sorted(set(flags) | {i.code for i in issues} | {"regenerated"})
        if any(i.severity in ("hedge", "flag", "block") for i in issues):
            final = final.rstrip() + guardrails.HEDGE_NOTE

    # ---- post-generation escalations (dedup against what the Coordinator raised) ----
    raised = {e.get("trigger") for e in state.get("escalations", [])}
    post_esc = guardrails.evaluate_escalation(
        state=state, user_text=state.get("user_input", ""),
        distress="", high_stakes="", sensitive=[], profile_conflict=[],
        post_gen_issues=issues, already_raised=raised,
    )
    for e in post_esc:
        audit_log.log_event(sid, "escalation", trigger=e.trigger, risk=e.risk)
    updates: Dict[str, Any] = {"guardrail_flags": flags}
    if post_esc:
        updates["escalations"] = [{**e.as_dict(), "turn": len(state.get("messages", [])) // 2 + 1}
                                  for e in post_esc]

    # ---- surface an escalation notice to the student ----
    # Only for HIGH-risk escalations RAISED THIS TURN on a task route. Escalations
    # accumulate in state for the whole conversation (audit trail), so an earlier
    # turn's High escalation (e.g. a discovery hallucination) must not keep
    # re-flagging every later essay / discovery answer. Medium ones (underpopulated
    # profile, sensitive disclosure, profile contradiction) are logged for the
    # reviewer and handled inline (confirm flow / human offer) - a scary "flagged
    # for review" banner on a "what's your major?" prompt is not helpful.
    current_turn = len(state.get("messages", [])) // 2 + 1
    merged_esc = list(state.get("escalations", [])) + [
        {**e.as_dict(), "turn": current_turn} for e in post_esc
    ]
    highs = guardrails.high_escalations_this_turn(
        merged_esc, current_turn, state.get("user_input", "")
    )
    show_notice = (
        route not in ("support", "planning")
        and intent not in ("out_of_scope", "resume", "help", "human_handoff", "confirm_profile")
        and highs
        and len((state.get("response") or "")) > 200   # not a one-line clarifying question
    )
    if show_notice and guardrails.ESCALATION_NOTICE.strip() not in final:
        final = final.rstrip() + guardrails.ESCALATION_NOTICE

    if final != text:
        updates["response"] = final

    updates["messages"] = [{"role": "assistant", "content": final}]

    audit_log.log_event(
        sid, "post_gen", route=route, intent=intent,
        flags=flags, hedged=(final != text),
        escalations=[e["trigger"] for e in merged_esc],
    )
    return updates
