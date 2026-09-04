"""
Retrieval over essay_methodology.json for the Essay Agent.

Companion to essay_examples.py: that file holds *example essays* (what good
looks like); this one holds *coaching method* (paths, structures, craft
techniques, per-prompt strategy). Same tiny keyword scorer - a real system
would embed the cards, but college-essay method is a small, stable corpus.

Public entry points:
  diagnose_path(profile, disclosures, transcript)  -> ("A".."D", "narrative"|"montage")
  infer_stage(had_draft, draft_count, text)        -> "brainstorm"|"drafting"|"revising"
  retrieve_methodology(path=, structure=, stage=, prompt_set=, query=, k=) -> [card, ...]
  format_cards(cards)                              -> str  (for the LLM prompt)
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional

from config import ESSAY_METHODOLOGY_FILE

_STOP = set(
    "the a an and or of to in for with my your our i is it that this on at as you "
    "be are was were have has had do does what when where how why who which not".split()
)

# ---------------------------------------------------------------------------
# corpus
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _cards() -> List[Dict[str, Any]]:
    with open(ESSAY_METHODOLOGY_FILE, "r") as f:
        return json.load(f).get("cards", [])


def _tokens(text: str) -> set:
    return {w for w in re.findall(r"[a-z]+", text.lower()) if w not in _STOP and len(w) > 2}


# ---------------------------------------------------------------------------
# diagnosis  (deterministic - no LLM)
# ---------------------------------------------------------------------------

# sensitive-disclosure categories that count as "a significant challenge" for
# path routing (mental_health / safety are handled by the support node, not here)
_CHALLENGE_CATEGORIES = {"immigration_status", "family_trauma", "financial_hardship"}

_CHALLENGE_KW = (
    "first gen", "first-gen", "first generation", "single parent", "single mom",
    "single dad", "raised by", "work to support", "working to support",
    "support my family", "pay the bills", "paid the bills", "two jobs",
    "undocumented", "daca", "refugee", "asylum", "moved to the us", "immigrated",
    "english is not my", "english isn't my", "low income", "low-income",
    "can't afford", "cant afford", "evicted", "homeless", "caregiver",
    "take care of my", "parent lost", "parent's job", "parents' job", "disability",
    "learning difference", "iep", "504 plan",
)

_KNOWS_MAJOR_KW = (
    "i want to study", "i want to major", "planning to study", "planning to major",
    "my major", "major in", "study engineering", "pre-med", "premed",
    "want to be a", "want to become a", "career in", "go into",
)
_UNDECIDED_KW = (
    "not sure what", "don't know what i want to study", "dont know what i want to study",
    "undecided", "haven't decided", "havent decided", "still figuring out",
    "no idea what i want to", "open to anything",
)

_STARTED_DRAFT_KW = (
    "i started", "i've started", "ive started", "my draft", "first draft",
    "rough draft", "so far i wrote", "i wrote", "here's what i have",
    "heres what i have", "working on a draft",
)
_REVISING_KW = (
    "revise", "revising", "another draft", "next draft", "feedback again",
    "second draft", "third draft", "made changes", "updated it", "reworked",
)


def _has_challenge(profile: Dict[str, Any], disclosures: List[Dict[str, Any]],
                   transcript: str) -> bool:
    if profile.get("is_first_gen") or profile.get("needs_financial_aid"):
        return True
    for d in disclosures or []:
        if d.get("category") in _CHALLENGE_CATEGORIES:
            return True
    t = transcript.lower()
    return any(k in t for k in _CHALLENGE_KW)


def _knows_major(profile: Dict[str, Any], transcript: str) -> bool:
    major = (profile.get("major") or "").strip().lower()
    if major and major not in ("undecided", "undeclared", "unknown", "n/a", "none"):
        return True
    t = transcript.lower()
    if any(k in t for k in _UNDECIDED_KW):
        return False
    return any(k in t for k in _KNOWS_MAJOR_KW)


def diagnose_path(profile: Optional[Dict[str, Any]],
                  disclosures: Optional[List[Dict[str, Any]]] = None,
                  transcript: str = "") -> tuple:
    """Return (path, structure). path in {A,B,C,D}; structure in {narrative,montage}.

    A = challenge + known major       (narrative)
    B = no challenge + known major    (montage)
    C = challenge + undecided         (narrative)
    D = no challenge + undecided      (montage)
    """
    profile = profile or {}
    challenge = _has_challenge(profile, disclosures or [], transcript)
    major = _knows_major(profile, transcript)
    path = {(True, True): "A", (False, True): "B",
            (True, False): "C", (False, False): "D"}[(challenge, major)]
    structure = "narrative" if path in ("A", "C") else "montage"
    return path, structure


def infer_stage(had_draft: bool, draft_count: int = 0, text: str = "") -> str:
    """brainstorm (no draft yet) -> drafting (has/starting a draft) -> revising."""
    t = (text or "").lower()
    if had_draft:
        return "revising" if draft_count > 1 or any(k in t for k in _REVISING_KW) else "drafting"
    if any(k in t for k in _REVISING_KW):
        return "revising"
    if any(k in t for k in _STARTED_DRAFT_KW):
        return "drafting"
    return "brainstorm"


def detect_prompt_set(text: str) -> str:
    """'uc_piq' | 'common_app' | '' from the student's wording."""
    t = (text or "").lower()
    if any(k in t for k in ("uc ", "u.c.", "university of california", "piq",
                            "personal insight", "berkeley essay", "ucla essay")):
        return "uc_piq"
    if any(k in t for k in ("common app", "commonapp", "common application",
                            "personal statement", "coalition")):
        return "common_app"
    return ""


# ---------------------------------------------------------------------------
# retrieval
# ---------------------------------------------------------------------------


def retrieve_methodology(*, path: str = "", structure: str = "", stage: str = "",
                         prompt_set: str = "", query: str = "",
                         kinds: Optional[List[str]] = None, k: int = 4) -> List[Dict[str, Any]]:
    """Top-k methodology cards for the student's situation."""
    q_tokens = _tokens(query)
    scored = []
    for card in _cards():
        if kinds and card.get("kind") not in kinds:
            continue
        applies = card.get("applies_to", {})
        score = 0.0

        # a filter that is present on the card must match (empty list == "any")
        for key, want in (("path", path), ("structure", structure),
                          ("stage", stage), ("prompt_set", prompt_set)):
            allowed = applies.get(key)
            if allowed:
                if want and want in allowed:
                    score += {"path": 3, "structure": 3,
                              "stage": 2, "prompt_set": 3}[key]
                elif want:
                    # card is scoped to a different value -> push down. A stage
                    # mismatch is a soft nudge (stages bleed together); a wrong
                    # path or prompt-set is a near-veto.
                    score -= 2 if key == "stage" else 5

        blob = _tokens(card.get("title", "")) | _tokens(" ".join(card.get("themes", []))) \
            | _tokens(card.get("summary", ""))
        score += len(q_tokens & blob)

        # always surface the core path + structure cards a little
        if card.get("kind") in ("path", "structure") and not query:
            score += 0.5

        if score > 0:
            scored.append((score, card))

    scored.sort(key=lambda s: s[0], reverse=True)
    out = [c for _, c in scored[:k]]
    return out or _cards()[:1]


def format_cards(cards: List[Dict[str, Any]]) -> str:
    """Compact rendering for the Essay Agent's prompt."""
    if not cards:
        return ""
    lines = []
    for c in cards:
        lines.append(f"### {c.get('title', c.get('id', ''))}")
        lines.append(c.get("summary", "").strip())
        qs = c.get("prompts_for_student") or []
        if qs:
            lines.append("Questions you could ask the student: "
                         + " / ".join(q.strip() for q in qs[:3]))
        lines.append("")
    return "\n".join(lines).strip()


PATH_BLURB = {
    "A": "faced significant challenges and has a sense of what they want to study",
    "B": "has not flagged a significant challenge and knows what they want to study",
    "C": "faced significant challenges and is still undecided on a major",
    "D": "has not flagged a significant challenge and is undecided on a major",
}
