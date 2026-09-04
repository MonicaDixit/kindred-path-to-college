"""
Planning Agent node (deterministic, NO LLM).

Checkpoint 5, Agent 3: build an actionable week-by-week timeline.
  - days remaining to each deadline
  - sort by urgency
  - week-by-week task plan (essay drafts + application submit)
  - flag workload conflicts (two deadlines in the same week)
  - factor in essay status from shared state

Always the same output for the same input. Zero tokens.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, List

import college_repo
from kindred_state import KindredState


def _selected(state: KindredState) -> List[str]:
    ids = state.get("selected_colleges") or state.get("discussed_colleges") or []
    return [c for c in ids if college_repo.deadline_of(c)]


def _format_timeline(state: KindredState) -> Dict[str, Any]:
    today = _dt.date.today()
    colleges = _selected(state)
    if not colleges:
        return {"error": "no_colleges"}

    rows = []
    for cid in colleges:
        dl_str = state.get("college_deadlines", {}).get(cid) or college_repo.deadline_of(cid)
        try:
            dl = _dt.date.fromisoformat(dl_str)
        except (TypeError, ValueError):
            continue
        essay_rec = state.get("essays", {}).get(cid, {})
        rows.append({
            "college_id": cid,
            "college": college_repo.name_of(cid),
            "deadline": dl_str,
            "days_left": (dl - today).days,
            "week_of_deadline": dl.isocalendar()[1],
            "year_of_deadline": dl.isocalendar()[0],
            "essays_required": college_repo.get(cid).get("admissions", {}).get("essays_required", 0),
            "essay_status": essay_rec.get("status", "not_started"),
            "drafts_done": len(essay_rec.get("drafts", [])),
        })

    rows.sort(key=lambda r: r["days_left"])

    # conflict detection: same iso (year, week)
    seen: Dict[tuple, List[str]] = {}
    for r in rows:
        seen.setdefault((r["year_of_deadline"], r["week_of_deadline"]), []).append(r["college"])
    conflicts = [v for v in seen.values() if len(v) > 1]

    # week-by-week plan: for each college, work back from its deadline
    weekly: Dict[str, List[str]] = {}

    def _add(week_start: _dt.date, task: str):
        key = week_start.isoformat()
        weekly.setdefault(key, []).append(task)

    def _monday(d: _dt.date) -> _dt.date:
        return d - _dt.timedelta(days=d.weekday())

    for r in rows:
        dl = _dt.date.fromisoformat(r["deadline"])
        submit_week = _monday(dl - _dt.timedelta(days=3))
        polish_week = _monday(dl - _dt.timedelta(days=10))
        draft_week = _monday(dl - _dt.timedelta(days=24))
        if r["essays_required"] and r["drafts_done"] == 0:
            _add(draft_week, f"{r['college']}: write first draft of {r['essays_required']} essay(s)")
            _add(polish_week, f"{r['college']}: revise essay(s) with Kindred feedback")
        elif r["essays_required"]:
            _add(polish_week, f"{r['college']}: revise essay draft #{r['drafts_done']} -> next draft")
        _add(submit_week, f"{r['college']}: final review + SUBMIT application (due {r['deadline']})")

    plan = [
        {"week_of": wk, "tasks": sorted(set(tasks))}
        for wk, tasks in sorted(weekly.items())
        if _dt.date.fromisoformat(wk) >= _monday(today) - _dt.timedelta(days=7)
    ]

    urgent = [r["college"] for r in rows if 0 <= r["days_left"] <= 21]

    return {
        "generated_on": today.isoformat(),
        "deadline_order": rows,
        "conflicts": conflicts,
        "urgent": urgent,
        "weekly_plan": plan,
    }


def _render(timeline: Dict[str, Any]) -> str:
    if timeline.get("error") == "no_colleges":
        return (
            "I don't have any colleges with deadlines yet. Ask me to build your "
            "college list first (\"I'm pre-med, 3.2 GPA - give me colleges\"), then "
            "I can plan your weeks."
        )
    lines = [f"YOUR APPLICATION TIMELINE  (as of {timeline['generated_on']})", "=" * 60, ""]
    lines.append("DEADLINE ORDER (most urgent first):")
    for i, r in enumerate(timeline["deadline_order"], 1):
        flag = "  ⚠ URGENT" if r["college"] in timeline["urgent"] else ""
        lines.append(
            f"  {i}. {r['college']:<24} {r['deadline']}  "
            f"({r['days_left']} days, {r['essays_required']} essay(s), "
            f"{r['essay_status']}){flag}"
        )
    if timeline["conflicts"]:
        lines += ["", "WORKLOAD CONFLICTS (same week):"]
        for grp in timeline["conflicts"]:
            lines.append(f"  • {' + '.join(grp)} - stagger your drafts")
    lines += ["", "WEEK-BY-WEEK PLAN:"]
    for wk in timeline["weekly_plan"]:
        lines.append(f"  Week of {wk['week_of']}:")
        for t in wk["tasks"]:
            lines.append(f"     - {t}")
    lines += ["", "Add or remove colleges anytime and I'll rebuild this."]
    return "\n".join(lines)


def planning_node(state: KindredState) -> Dict[str, Any]:
    timeline = _format_timeline(state)
    text = _render(timeline)
    return {
        "response": text,
        "timeline": timeline,
    }
