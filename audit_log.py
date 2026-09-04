"""
Turn-level trajectory logging (Checkpoint 6).

Every turn appends one JSON line to `guardrail_audit.jsonl`, creating a
recoverable audit trail. `metrics.py` reads this file to compute the evaluation
metrics (groundedness, escalation rate, distress-handoff frequency, ...).

Records are intentionally low-cardinality: we log guardrail *events* and short
snippets, not full student essays or profiles.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import threading
from pathlib import Path
from typing import Any, Dict

from config import PROJECT_ROOT

AUDIT_FILE = Path(os.getenv("GUARDRAIL_AUDIT_FILE", PROJECT_ROOT / "guardrail_audit.jsonl"))
_LOCK = threading.Lock()

# keep snippets short - this file is an operational log, not a data store
_SNIPPET = 240


def _clip(text: Any) -> Any:
    if isinstance(text, str) and len(text) > _SNIPPET:
        return text[:_SNIPPET] + "…"
    return text


def log_event(session_id: str, event: str, **fields: Any) -> None:
    """Append one audit record. `event` is a short kind, e.g. 'turn',
    'escalation', 'distress_handoff', 'post_gen_flag', 'sensitive_disclosure'."""
    record: Dict[str, Any] = {
        "ts": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "session": session_id,
        "event": event,
    }
    for k, v in fields.items():
        record[k] = _clip(v)
    line = json.dumps(record, ensure_ascii=False, default=str)
    with _LOCK:
        with open(AUDIT_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def read_all() -> list[Dict[str, Any]]:
    if not AUDIT_FILE.exists():
        return []
    out = []
    with open(AUDIT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return out
