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

    # week-by-week plan: for each college, work back from its deadline. Each row
    # is structured (not a pre-formatted string) so _render can lay it out as a
    # table - college / task / deadline / the week it falls in.
    weekly: List[Dict[str, str]] = []

    def _add(week_start: _dt.date, college: str, task: str, deadline: str):
        weekly.append({
            "week_of": week_start.isoformat(),
            "college": college,
            "task": task,
            "deadline": deadline,
        })

    def _monday(d: _dt.date) -> _dt.date:
        return d - _dt.timedelta(days=d.weekday())

    for r in rows:
        dl = _dt.date.fromisoformat(r["deadline"])
        submit_week = _monday(dl - _dt.timedelta(days=3))
        polish_week = _monday(dl - _dt.timedelta(days=10))
        draft_week = _monday(dl - _dt.timedelta(days=24))
        if r["essays_required"] and r["drafts_done"] == 0:
            _add(draft_week, r["college"], f"Write first draft of {r['essays_required']} essay(s)", r["deadline"])
            _add(polish_week, r["college"], "Revise essay(s) with Kindred feedback", r["deadline"])
        elif r["essays_required"]:
            _add(polish_week, r["college"], f"Revise essay draft #{r['drafts_done']} → next draft", r["deadline"])
        _add(submit_week, r["college"], "Final review + submit application", r["deadline"])

    cutoff = (_monday(today) - _dt.timedelta(days=7)).isoformat()
    seen_rows: set = set()
    plan: List[Dict[str, str]] = []
    for row in sorted(weekly, key=lambda w: (w["week_of"], w["deadline"], w["college"])):
        if row["week_of"] < cutoff:
            continue
        key = (row["week_of"], row["college"], row["task"])
        if key in seen_rows:
            continue
        seen_rows.add(key)
        plan.append(row)

    urgent = [r["college"] for r in rows if 0 <= r["days_left"] <= 21]

    return {
        "generated_on": today.isoformat(),
        "deadline_order": rows,
        "conflicts": conflicts,
        "urgent": urgent,
        "weekly_plan": plan,
    }


def _pretty_date(iso: str) -> str:
    try:
        d = _dt.date.fromisoformat(iso)
    except (TypeError, ValueError):
        return iso
    return d.strftime("%b %d").replace(" 0", " ")


def _render(timeline: Dict[str, Any]) -> str:
    if timeline.get("error") == "no_colleges":
        return (
            "I don't have any colleges with deadlines yet. Ask me to build your "
            "college list first (\"I'm pre-med, 3.2 GPA - give me colleges\"), then "
            "I can plan your weeks."
        )
    lines = [f"### Your application timeline  \n_as of {timeline['generated_on']}_", ""]

    lines.append("**Deadline order** (most urgent first)")
    lines.append("")
    lines.append("| # | College | Deadline | Days left | Essays | Status |")
    lines.append("|---|---|---|---|---|---|")
    for i, r in enumerate(timeline["deadline_order"], 1):
        flag = " ⚠️" if r["college"] in timeline["urgent"] else ""
        lines.append(
            f"| {i} | {r['college']}{flag} | {_pretty_date(r['deadline'])} | "
            f"{r['days_left']} | {r['essays_required']} | {r['essay_status']} |"
        )

    if timeline["conflicts"]:
        lines += ["", "**Workload conflicts** (same week)"]
        for grp in timeline["conflicts"]:
            lines.append(f"- {' + '.join(grp)} — stagger your drafts")

    lines += ["", "**Week-by-week plan**", ""]
    if timeline["weekly_plan"]:
        lines.append("| Week of | Task | College | Deadline |")
        lines.append("|---|---|---|---|")
        for row in timeline["weekly_plan"]:
            lines.append(
                f"| {_pretty_date(row['week_of'])} | {row['task']} | "
                f"{row['college']} | {_pretty_date(row['deadline'])} |"
            )
    else:
        lines.append("_Nothing due soon enough to plan a week for yet._")

    lines += ["", "Add or remove colleges anytime and I'll rebuild this."]
    return "\n".join(lines)


def planning_node(state: KindredState) -> Dict[str, Any]:
    timeline = _format_timeline(state)
    text = _render(timeline)
    return {
        "response": text,
        "timeline": timeline,
    }
