"""Lookup tables for the College Scorecard ETL (scripts/build_colleges.py)."""

from __future__ import annotations

from typing import Dict, List, Optional

# --- Scorecard program_percentage family -> Kindred major labels -------------
# We say a school "offers" a major if the mapped family's enrolment share > 0.
CIP_FAMILY_TO_MAJORS: Dict[str, List[str]] = {
    "computer": ["Computer Science"],
    "engineering": ["Engineering"],
    "engineering_technology": ["Engineering"],
    "mathematics": ["Mathematics"],
    "biological": ["Biology", "Pre-Med"],
    "physical_science": ["Physics", "Chemistry"],
    "health": ["Nursing", "Pre-Med"],
    "business_marketing": ["Business", "Economics"],
    "social_science": ["Political Science", "Economics", "Sociology"],
    "psychology": ["Psychology"],
    "visual_performing": ["Art"],
    "english": ["English"],
    "history": ["History"],
    "humanities": ["Liberal Arts"],
    "multidiscipline": ["Liberal Arts"],
    "philosophy_religious": ["Philosophy"],
    "education": ["Education"],
    "communication": ["Communications", "Journalism"],
    "public_administration_social_service": ["Social Work"],
    "security_law_enforcement": ["Criminal Justice"],
    "legal": ["Pre-Law"],
}

# families that count toward a "STEM-strong" flag
_STEM_FAMILIES = ("computer", "engineering", "engineering_technology",
                  "mathematics", "biological", "physical_science")


def majors_from_program_mix(mix: Dict[str, Optional[float]]) -> List[str]:
    out: List[str] = []
    for fam, share in (mix or {}).items():
        if share and share > 0.0:
            for m in CIP_FAMILY_TO_MAJORS.get(fam, []):
                if m not in out:
                    out.append(m)
    return sorted(out)


def stem_strength(mix: Dict[str, Optional[float]]) -> bool:
    return sum((mix or {}).get(f) or 0.0 for f in _STEM_FAMILIES) >= 0.30


# --- geography --------------------------------------------------------------
_NORTHEAST = {"CT", "ME", "MA", "NH", "RI", "VT", "NJ", "NY", "PA"}
_MIDWEST = {"IL", "IN", "MI", "OH", "WI", "IA", "KS", "MN", "MO", "NE", "ND", "SD"}
_SOUTH = {"DE", "FL", "GA", "MD", "NC", "SC", "VA", "DC", "WV", "AL", "KY",
          "MS", "TN", "AR", "LA", "OK", "TX"}
_WEST = {"AZ", "CO", "ID", "MT", "NV", "NM", "UT", "WY", "AK", "CA", "HI",
         "OR", "WA"}


def region_of(state: Optional[str]) -> str:
    s = (state or "").upper()
    if s in _NORTHEAST:
        return "Northeast"
    if s in _MIDWEST:
        return "Midwest"
    if s in _SOUTH:
        return "South"
    if s in _WEST:
        return "West"
    return "Unknown"


def setting_of(locale: Optional[int]) -> str:
    """NCES locale code -> coarse setting."""
    if locale is None:
        return "unknown"
    tens = int(locale) // 10
    return {1: "urban", 2: "suburban", 3: "town", 4: "rural"}.get(tens, "unknown")


def size_bucket(n: Optional[int]) -> str:
    if not n:
        return "unknown"
    if n < 3000:
        return "small"
    if n <= 12000:
        return "medium"
    return "large"


OWNERSHIP = {1: "public", 2: "private nonprofit", 3: "private for-profit"}

# Carnegie basic classification codes for doctoral / research universities
_RESEARCH_CARNEGIE = {15, 16, 17}


def is_research(carnegie_basic: Optional[int], size: Optional[int]) -> bool:
    if carnegie_basic in _RESEARCH_CARNEGIE:
        return True
    return bool(size and size > 15000)


# income bands used for net-price-by-income (Scorecard keys)
INCOME_BANDS = ["0-30000", "30001-48000", "48001-75000", "75001-110000", "110001-plus"]
