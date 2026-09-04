"""
Discovery Agent node (LLM + RAG retrieval).

Checkpoint 5, Agent 1: help students explore colleges that match their profile.
  - Retrieves similar student cases + major strategy (RAG over case studies)
  - Scores each candidate college with the statistical ranker
  - Categorizes into reach / target / safety
  - Calls the LLM once to turn the structured analysis into a personalized,
    conversational answer that references colleges already discussed.
"""

from __future__ import annotations

from typing import Any, Dict, List

import college_repo
import guardrails
from case_study_retrieval import get_major_specific_strategy, retrieve_similar_cases
from college_tools_enhanced import db, get_college_guidance, rank_college_fit
from config import CANDIDATE_COLLEGES, DISCOVERY_SHORTLIST_SIZE, NET_PRICE_CEILING
from kindred_state import KindredState
from llm_client import OpenRouterClient

_llm = OpenRouterClient()

_SYSTEM = (
    "You are Kindred's Discovery counselor for first-generation and low-income "
    "students. You are warm, specific, and honest. You are given structured fit "
    "analysis that was already computed - do not invent numbers. "
    "CRITICAL: only discuss colleges that appear in the structured analysis you are "
    "given. Never introduce other schools. If a category (reach/target/safety) has "
    "no colleges, say so plainly and note that the current list skews selective. "
    "Explain fit in plain language, reference the student's background, and keep it "
    "conversational (the student asks one question at a time)."
    + guardrails.DISCOVERY_GUARDRAILS
)


def _all_sensitive_kws() -> tuple:
    return tuple(k for kws in guardrails.SENSITIVE_CATEGORIES.values() for k in kws)


def _has_sensitive(text: str) -> bool:
    t = (text or "").lower()
    return any(k in t for k in _all_sensitive_kws())


def _safe_query(state: KindredState) -> str:
    """Per Checkpoint 6: a sensitive personal disclosure is NOT passed to the
    Discovery Agent as a signal. If THIS message carries one, hand the LLM a
    neutral description of the request instead of the raw text."""
    ui = state.get("user_input", "")
    if _has_sensitive(ui):
        return "(the student asked for college recommendations / list guidance)"
    return repr(ui)


def _safe_transcript(state: KindredState, n: int = 6) -> str:
    lines = _recent_transcript(state, n)
    kws = _all_sensitive_kws()
    kept = [ln for ln in lines.splitlines()
            if not (ln.startswith("Student:") and any(k in ln.lower() for k in kws))]
    return "\n".join(kept)


def _profile_gaps(profile: Dict[str, Any]) -> List[str]:
    gaps = []
    if not profile.get("gpa"):
        gaps.append("GPA")
    if not profile.get("major"):
        gaps.append("intended major")
    return gaps


def _income_band(profile: Dict[str, Any]) -> str | None:
    """Map the profile onto a Scorecard net-price income band. We only track a
    `needs_financial_aid` boolean, so use the low-income band as the proxy."""
    if profile.get("family_income_band"):
        return profile["family_income_band"]
    if profile.get("needs_financial_aid"):
        return "0-30000"
    return None


def _rank_all(profile: Dict[str, Any], ids: List[str]) -> List[Dict[str, Any]]:
    needs_aid = bool(profile.get("needs_financial_aid"))
    band = _income_band(profile)
    out = []
    for cid in ids:
        try:
            r = rank_college_fit(
                college_id=cid,
                student_gpa=float(profile.get("gpa", 0) or 0) or None,
                student_sat=int(profile.get("sat_score", 0) or 0) or None,
                student_major=profile.get("major"),
                is_first_gen=bool(profile.get("is_first_gen", False)),
                needs_financial_aid=needs_aid,
                income_band=band,
            )
            r["id"] = cid
            out.append(r)
        except Exception as e:  # noqa: BLE001 - keep the agent resilient
            out.append({"college": college_repo.name_of(cid), "id": cid, "error": str(e)})
    return out


def _assemble_list(buckets: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Pick a balanced, ordered list from the scored buckets: ~4 reach / 4 target
    / 3 safety, best-match first within each. Guarantee at least one safety."""
    picked = buckets["reach"][:4] + buckets["target"][:4] + buckets["safety"][:3]
    if not buckets["safety"]:
        # fall back to the most-likely admits from target as "closest to safety"
        picked += [dict(r, category="target (closest to a safety)")
                   for r in buckets["target"][4:6]]
    return picked


def _bucket(ranked: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    buckets = {"reach": [], "target": [], "safety": []}
    for r in ranked:
        buckets.get(r.get("category", "reach"), buckets["reach"]).append(r)
    for b in buckets.values():
        b.sort(key=lambda r: r.get("fit_score", 0), reverse=True)
    return buckets


def _discovery_list(state: KindredState) -> Dict[str, Any]:
    profile = state.get("student_profile", {})
    gaps = _profile_gaps(profile)
    if gaps:
        msg = (
            "Before I can build your college list I need a bit more: "
            + " and ".join(gaps)
            + ". For example: \"I'm pre-med, 3.2 GPA, 1300 SAT, first-gen.\""
        )
        return {"response": msg}

    similar = retrieve_similar_cases(
        student_major=profile.get("major"),
        student_challenges=[],
        is_first_gen=bool(profile.get("is_first_gen", False)),
    )
    strategy = get_major_specific_strategy(profile.get("major", "Undecided"))

    # Stage A: candidate generation from the full pool (affordable + relevant)
    shortlist = db.shortlist(
        major=profile.get("major"),
        needs_financial_aid=bool(profile.get("needs_financial_aid")),
        income_band=_income_band(profile),
        max_net_price=NET_PRICE_CEILING,
        limit=DISCOVERY_SHORTLIST_SIZE,
    ) or [{"id": cid} for cid in CANDIDATE_COLLEGES]  # fallback if pool is tiny

    ranked = [r for r in _rank_all(profile, [c["id"] for c in shortlist])
              if not r.get("error")]
    buckets = _bucket(ranked)
    picked = _assemble_list(buckets)

    def _fmt(r: Dict[str, Any]) -> Dict[str, Any]:
        ctx = r.get("context", {})
        return {
            "college": r["college"],
            "match_score": r.get("fit_score"),
            "est_admit_chance": ctx.get("est_admit_probability"),
            "your_stats_vs_school": ctx.get("academic_position"),
            "net_price": ctx.get("net_price_estimate"),
            "why": r.get("reasoning", [])[:3],
        }

    context = {
        "student_profile": profile,
        "similar_cases": similar.get("similar_cases", [])[:2],
        "major_strategy": strategy.get("what_schools_value", [])[:4],
        "list": {
            "reach": [_fmt(r) for r in picked if r.get("category") == "reach"],
            "target": [_fmt(r) for r in picked if str(r.get("category", "")).startswith("target")],
            "safety": [_fmt(r) for r in picked if r.get("category") == "safety"],
        },
    }

    prompt = (
        f"Student query: {_safe_query(state)}\n\n"
        f"Structured analysis (already computed):\n{context}\n\n"
        "Write a personalized response: a one-line read on their profile "
        "(reference their stats position and, if relevant, affordability), then "
        "REACH / TARGET / SAFETY sections listing ONLY the schools under each "
        "category in `list` above (never add others; if a bucket is empty, say so). "
        "One sentence of reasoning per school grounded in the fit data, including "
        "the net price when the student needs aid. Note est_admit_chance is a rough "
        "estimate, not a prediction. End with one concrete next step. Mention 1 "
        "relevant similar-student case briefly."
    )
    answer = _llm.call([{"role": "user", "content": prompt}], _SYSTEM)

    selected = [r["id"] for r in picked if r.get("id")]
    deadlines = dict(state.get("college_deadlines", {}))
    for cid in selected:
        dl = college_repo.deadline_of(cid)
        if dl:
            deadlines[cid] = dl

    return {
        "response": answer,
        "selected_colleges": selected,
        "discussed_colleges": selected,
        "college_deadlines": deadlines,
    }


def _recent_transcript(state: KindredState, n: int = 6) -> str:
    msgs = state.get("messages", [])[-n:]
    who = {"user": "Student", "assistant": "Kindred"}
    return "\n".join(f"{who.get(m.get('role'), m.get('role'))}: {m.get('content', '')}" for m in msgs)


def _current_list(state: KindredState) -> List[Dict[str, Any]]:
    """Brief re-scored view of the colleges already on the student's list."""
    profile = state.get("student_profile", {})
    out = []
    for cid in state.get("selected_colleges", []):
        row = {"college": college_repo.name_of(cid), "deadline": college_repo.deadline_of(cid)}
        try:
            fit = rank_college_fit(
                college_id=cid,
                student_gpa=float(profile.get("gpa", 0) or 0) or None,
                student_sat=int(profile.get("sat_score", 0) or 0) or None,
                student_major=profile.get("major"),
                is_first_gen=bool(profile.get("is_first_gen", False)),
                needs_financial_aid=bool(profile.get("needs_financial_aid")),
                income_band=_income_band(profile),
            )
            row.update(category=fit.get("category"), fit_score=fit.get("fit_score"),
                       admit_probability=fit.get("confidence"),
                       net_price=fit.get("context", {}).get("net_price_estimate"))
        except Exception:  # noqa: BLE001
            pass
        out.append(row)
    return out


def _discovery_answer(state: KindredState) -> Dict[str, Any]:
    """Answer a specific college question or an open follow-up, in full context."""
    profile = state.get("student_profile", {})
    cid = state.get("focus_college") or (state.get("discussed_colleges") or [None])[-1]

    focus: Dict[str, Any] = {}
    deadline = None
    if cid:
        deadline = college_repo.deadline_of(cid)
        focus = {
            "college": college_repo.name_of(cid),
            "deadline": deadline,
            "guidance": get_college_guidance(
                college_id=cid,
                student_major=profile.get("major"),
                is_first_gen=bool(profile.get("is_first_gen", False)),
            ),
        }
        if profile.get("gpa") and profile.get("major"):
            try:
                focus["fit_for_student"] = rank_college_fit(
                    college_id=cid,
                    student_gpa=float(profile["gpa"]),
                    student_sat=int(profile.get("sat_score", 0) or 0),
                    student_major=profile.get("major"),
                    is_first_gen=bool(profile.get("is_first_gen", False)),
                )
            except Exception:  # noqa: BLE001
                pass

    context = {
        "student_profile": profile,
        "colleges_on_list": _current_list(state),
        "college_in_focus": focus or None,
        "recent_conversation": _safe_transcript(state),
    }
    prompt = (
        f"The student just asked: {_safe_query(state)}\n\n"
        f"Everything Kindred knows right now:\n{context}\n\n"
        "Answer their question directly and conversationally, grounded in the data "
        "above. Only discuss colleges that appear in the context. If they asked "
        "about cost/aid/deadline, give the concrete number. If they asked why "
        "certain schools were chosen or which fits best, explain using the fit "
        "scores. If you genuinely need more info from them, ask one short question."
    )
    answer = _llm.call([{"role": "user", "content": prompt}], _SYSTEM)

    updates: Dict[str, Any] = {
        "response": answer,
    }
    if cid:
        updates["focus_college"] = cid
    if cid and deadline:
        d = dict(state.get("college_deadlines", {}))
        d[cid] = deadline
        updates["college_deadlines"] = d
    return updates


def discovery_node(state: KindredState) -> Dict[str, Any]:
    if state.get("intent") == "college_discovery":
        return _discovery_list(state)
    # college_inquiry, discovery_followup
    return _discovery_answer(state)
