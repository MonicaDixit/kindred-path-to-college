"""
Tiny RAG layer over essay_examples.json for the Essay Agent.

Real implementation would embed excerpts in a vector store; here we score by
college match + theme/keyword overlap, which is enough for the conversational demo.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any, Dict, List

from config import ESSAY_EXAMPLES_FILE

_STOP = set("the a an and or of to in for with my your i is it that this on at as".split())


@lru_cache(maxsize=1)
def _examples() -> List[Dict[str, Any]]:
    with open(ESSAY_EXAMPLES_FILE, "r") as f:
        return json.load(f).get("examples", [])


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", text.lower()) if w not in _STOP and len(w) > 2}


def retrieve_essay_examples(college_id: str = "", query: str = "", k: int = 2) -> List[Dict[str, Any]]:
    """Return up to k example essays most relevant to the college + query."""
    q_tokens = _tokens(query)
    scored = []
    for ex in _examples():
        score = 0.0
        if college_id and ex.get("college") == college_id:
            score += 3.0
        if ex.get("college") == "common_app":
            score += 0.5  # generally applicable
        overlap = q_tokens & (_tokens(" ".join(ex.get("themes", []))) | _tokens(ex.get("excerpt", "")))
        score += len(overlap)
        if score > 0:
            scored.append((score, ex))
    scored.sort(key=lambda s: s[0], reverse=True)
    return [ex for _, ex in scored[:k]] or _examples()[:k]
