"""
Evaluation metrics for the Checkpoint 6 guardrails, computed from the audit
trail (`guardrail_audit.jsonl`).

    python3 metrics.py            # pretty-print
    GET /api/metrics              # same, as JSON

These close the feedback loop the doc describes: escalation trends, distress
handoff frequency, hedge / fallback rates, and Essay Agent observability tell
the team whether the guardrails are calibrated or need adjustment.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Any, Dict

import audit_log


def _pct(n: int, d: int) -> float:
    return round(100.0 * n / d, 1) if d else 0.0


def compute() -> Dict[str, Any]:
    rows = audit_log.read_all()
    if not rows:
        return {"note": "no audit data yet", "turns": 0}

    sessions = {r.get("session") for r in rows}
    by_event = Counter(r.get("event") for r in rows)

    turns = [r for r in rows if r.get("event") == "turn"]
    post_gen = [r for r in rows if r.get("event") == "post_gen"]
    escal = [r for r in rows if r.get("event") == "escalation"]

    sess_with = lambda ev: len({r["session"] for r in rows if r.get("event") == ev})

    # --- flag tallies from post-generation records ---
    flag_counter: Counter = Counter()
    hedged = 0
    for r in post_gen:
        for f in r.get("flags", []) or []:
            flag_counter[f] += 1
        if r.get("hedged"):
            hedged += 1

    essay_pg = [r for r in post_gen if r.get("route") == "essay"]
    discovery_pg = [r for r in post_gen if r.get("route") == "discovery"]
    planning_pg = [r for r in post_gen if r.get("route") == "planning"]

    def _flag_rate(subset, code):
        n = sum(1 for r in subset if code in (r.get("flags") or []))
        return {"count": n, "rate_pct": _pct(n, len(subset))}

    escal_triggers = Counter(r.get("trigger") for r in escal)

    return {
        "totals": {
            "sessions": len(sessions),
            "turns": len(turns),
            "events": dict(by_event),
        },
        "system_wide": {
            "escalation_rate_pct": _pct(sess_with("escalation"), len(sessions)),
            "distress_handoff_sessions": sess_with("distress_handoff"),
            "distress_handoff_rate_pct": _pct(sess_with("distress_handoff"), len(sessions)),
            "out_of_scope_turns": by_event.get("out_of_scope", 0),
            "sensitive_disclosure_sessions": sess_with("sensitive_disclosure"),
            "profile_conflict_sessions": sess_with("profile_conflict"),
            "human_handoff_requests": by_event.get("human_handoff_requested", 0),
            "hedge_rate_pct": _pct(hedged, len(post_gen)),
            "fallback_success_pct": _pct(
                len(post_gen) - sum(1 for r in post_gen if "hallucinated_college" in (r.get("flags") or [])),
                len(post_gen),
            ),
        },
        "escalation_triggers": dict(escal_triggers),
        "discovery_agent": {
            "responses": len(discovery_pg),
            "hallucinated_college": _flag_rate(discovery_pg, "hallucinated_college"),
            "overconfident_claim": _flag_rate(discovery_pg, "overconfident_claim"),
        },
        "essay_agent": {
            "responses": len(essay_pg),
            "sycophancy_flag": _flag_rate(essay_pg, "sycophancy"),
            "ghostwriting_flag": _flag_rate(essay_pg, "ghostwriting"),
            "fabricated_biography_flag": _flag_rate(essay_pg, "fabricated_biography"),
            "regenerated": _flag_rate(essay_pg, "regenerated"),
        },
        "planning_agent": {
            "responses": len(planning_pg),
            "deadline_arithmetic_flag": _flag_rate(planning_pg, "deadline_arithmetic"),
            "deadline_out_of_order_flag": _flag_rate(planning_pg, "deadline_out_of_order"),
            "past_deadline_flag": _flag_rate(planning_pg, "past_deadline"),
        },
        "all_flags": dict(flag_counter),
    }


if __name__ == "__main__":
    print(json.dumps(compute(), indent=2))
