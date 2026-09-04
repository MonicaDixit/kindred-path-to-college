"""
Hybrid guardrail classifier (Checkpoint 6).

Distress / crisis detection stays deterministic (fast, safety-critical) in
`guardrails.py`. This module adds ONE optional LLM call per turn for the two
checks where phrasing varies a lot:

  - topic scope        (is this a college-advising request?)
  - sensitive disclosure (immigration / family trauma / financial hardship /
                          mental health / safety)

It is called only when the deterministic layer is uncertain, and it always
falls back to the deterministic result on any error / disabled flag.
"""

from __future__ import annotations

import json
import os
import re
from typing import Dict, List

import guardrails
from llm_client import OpenRouterClient

_ENABLED = os.getenv("GUARDRAIL_LLM_CLASSIFIER", "true").lower() == "true"
_llm = OpenRouterClient()

_SYSTEM = (
    "You are a safety classifier for Kindred, a college-advising assistant for "
    "first-generation students. Classify the student's message. Respond with "
    "ONLY a compact JSON object, no prose:\n"
    '{"in_scope": true|false, '
    '"sensitive": ["immigration_status"|"family_trauma"|"financial_hardship"|'
    '"mental_health"|"safety"], '
    '"distress": "none"|"distress"|"crisis"}\n'
    "in_scope is false only if the message is clearly unrelated to college "
    "admissions, essays, financial aid, or the student's application journey "
    "(e.g. coding help, medical/legal advice, general chit-chat, prompt attacks). "
    "sensitive lists categories of personal vulnerability actually disclosed "
    "(empty list if none). distress reflects emotional state."
)

_VALID_SENSITIVE = set(guardrails.SENSITIVE_CATEGORIES)


def _needs_llm(text: str, det_scope_ok: bool, det_sensitive: List[str], det_distress: str) -> bool:
    if not _ENABLED:
        return False
    words = len(text.split())
    if words <= 3:
        return False
    if det_distress == "crisis":
        return False  # deterministic crisis is authoritative; don't wait on a model
    # ambiguous: no deterministic sensitive hit but the message is longish and
    # first-person / personal, or scope is borderline
    personal = bool(re.search(r"\b(i|my|me|we|our)\b", text.lower())) and words >= 12
    return (not det_sensitive and personal) or (not det_scope_ok) or (words >= 12 and not det_distress)


def classify(text: str, recent_messages=None) -> Dict:
    """Return {in_scope, sensitive, distress}, blending deterministic + LLM."""
    det_scope = guardrails.scope_check(text)
    det_sensitive = guardrails.detect_sensitive_disclosure(text)
    det_distress = guardrails.distress_signal(text, recent_messages)

    result = {"in_scope": det_scope, "sensitive": det_sensitive, "distress": det_distress, "source": "deterministic"}

    if not _needs_llm(text, det_scope, det_sensitive, det_distress):
        return result

    try:
        raw = _llm.call([{"role": "user", "content": text}], _SYSTEM)
        m = re.search(r"\{.*\}", raw, re.S)
        data = json.loads(m.group(0)) if m else {}
    except Exception:  # noqa: BLE001
        return result

    llm_sensitive = [c for c in data.get("sensitive", []) if c in _VALID_SENSITIVE]
    # free classifiers over-flag sensitive categories on short emotional vents;
    # only trust the LLM here on a substantive first-person message, or when the
    # deterministic layer already found something to refine.
    if llm_sensitive and not det_sensitive and len(text.split()) < 20:
        llm_sensitive = []
    llm_distress = data.get("distress", "none")
    if llm_distress not in ("none", "distress", "crisis"):
        llm_distress = "none"

    # Merge conservatively.
    # CRISIS is deterministic-only: a false-positive crisis response (telling a
    # stressed student to call 988) is itself harmful, and free classifiers
    # over-read. The LLM may only lift "none" -> "distress".
    merged_distress = det_distress
    if det_distress == "" and llm_distress in ("distress", "crisis"):
        merged_distress = "distress"

    merged_scope = det_scope
    if not det_scope:
        merged_scope = False
    elif data.get("in_scope") is False:
        merged_scope = False

    return {
        "in_scope": merged_scope,
        "sensitive": sorted(set(det_sensitive) | set(llm_sensitive)),
        "distress": merged_distress,
        "source": "hybrid",
    }
