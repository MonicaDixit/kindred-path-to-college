"""
Thin read-only accessor over colleges_enhanced.json.

Used by the deterministic components (Coordinator, Planning agent) that need
college names / deadlines without going through the LLM ranking path.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional

from config import COLLEGE_DATA_FILE


@lru_cache(maxsize=1)
def _colleges() -> List[Dict[str, Any]]:
    with open(COLLEGE_DATA_FILE, "r") as f:
        return json.load(f).get("colleges", [])


def all_ids() -> List[str]:
    return [c["id"] for c in _colleges()]


def get(college_id: str) -> Optional[Dict[str, Any]]:
    cid = college_id.lower()
    for c in _colleges():
        if c["id"] == cid:
            return c
    return None


def name_of(college_id: str) -> str:
    c = get(college_id)
    return c["name"] if c else college_id


def _raw_deadline(college_id: str) -> Optional[str]:
    c = get(college_id)
    if not c:
        return None
    return c.get("admissions", {}).get("application_deadline") or c.get("application_deadline")


def deadline_of(college_id: str, today: Optional[_dt.date] = None) -> Optional[str]:
    """Application deadline as an ISO date, rolled forward to the next cycle that
    is still in the future (the JSON ships fixed 2024/2025 dates)."""
    raw = _raw_deadline(college_id)
    if not raw:
        return None
    today = today or _dt.date.today()
    try:
        d = _dt.date.fromisoformat(raw)
    except ValueError:
        return raw
    while d < today:
        try:
            d = d.replace(year=d.year + 1)
        except ValueError:  # Feb 29
            d = d.replace(year=d.year + 1, day=28)
    return d.isoformat()


# words too ambiguous to be a standalone school alias (state names, directions,
# generic terms) - the pool has hundreds of schools, so a bare "washington" or
# "state" must not resolve to one institution.
_AMBIGUOUS_SHORT = {
    "washington", "california", "michigan", "florida", "texas", "virginia",
    "carolina", "college", "state", "institute", "technology", "north", "south",
    "east", "west", "central", "national", "american", "international", "city",
    "new", "saint", "mount", "pacific", "atlantic", "union", "trinity",
}


@lru_cache(maxsize=1)
def _alias_map() -> Dict[str, str]:
    """Lowercase alias -> canonical college id. Aliases are matched on word
    boundaries. With a large pool we only add a short alias when it is long
    enough and unambiguous and not already claimed."""
    aliases: Dict[str, str] = {}
    for c in _colleges():
        cid = c["id"]
        aliases.setdefault(cid, cid)
        aliases.setdefault(c["name"].lower(), cid)
        short = c["name"].lower()
        for stop in (" university", "university of ", "the ", " at ", ", ",
                     "-main campus", "-seattle campus"):
            short = short.replace(stop, " ")
        short = re.sub(r"\s+", " ", short).strip()
        if len(short) >= 6 and short not in _AMBIGUOUS_SHORT and short not in aliases:
            aliases[short] = cid
    # hand-tuned, whole-word nicknames (win over generated aliases)
    aliases.update({
        "uc berkeley": "berkeley", "ucb": "berkeley", "cal": "berkeley",
        "stanford": "stanford", "the farm": "stanford",
        "caltech": "caltech", "cal tech": "caltech",
        "udub": "uw", "u dub": "uw", "uw": "uw", "uw seattle": "uw",
        "ut austin": "ut-austin", "ut-austin": "ut-austin", "ut": "ut-austin",
        "uiuc": "uiuc", "urbana": "uiuc", "urbana-champaign": "uiuc", "u of i": "uiuc",
        "mit": "massachusetts-institute-technology",
        "ucla": "california-los-angeles", "penn": "pennsylvania",
        "gt": "georgia-institute-technology", "georgia tech": "georgia-institute-technology",
    })
    # only keep hand-tuned nicknames whose target actually exists in the pool
    ids = {c["id"] for c in _colleges()}
    return {a: cid for a, cid in aliases.items() if cid in ids}


def resolve(text: str) -> List[str]:
    """Return every college id mentioned in `text`, in order of first appearance."""
    t = text.lower()
    hits: List[tuple] = []  # (position, cid)
    for alias, cid in _alias_map().items():
        m = re.search(rf"(?<![\w-]){re.escape(alias)}(?![\w-])", t)
        if m:
            hits.append((m.start(), cid))
    hits.sort()
    seen: List[str] = []
    for _, cid in hits:
        if cid not in seen:
            seen.append(cid)
    return seen
