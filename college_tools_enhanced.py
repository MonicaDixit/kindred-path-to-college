"""
Enhanced College Tools - With Statistical Analysis & RAG Support
Replaces college_tools.py with smarter ranking and percentile analysis
"""

import json
import math
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass
from config import COLLEGE_DATA_FILE

@dataclass
class CollegeFitAnalysis:
    """Structured result of college fit analysis"""
    college_name: str
    fit_score: float  # 0-100
    category: str  # reach, target, safety
    confidence: float  # 0-1 likelihood of admission
    
    gpa_fit: float
    sat_fit: float
    major_fit: float
    selectivity_adjustment: float
    support_fit: float
    
    reasoning: List[str]
    guidance_tips: List[str]
    context: Dict[str, Any]

class EnhancedCollegeDatabase:
    """Enhanced college database with statistical analysis"""
    
    def __init__(self, data_file: Path = COLLEGE_DATA_FILE):
        self.colleges = []
        self.load_colleges(data_file)
    
    def load_colleges(self, data_file: Path):
        """Load college data from JSON file"""
        if not data_file.exists():
            print(f"Warning: College data file not found at {data_file}")
            return
        
        with open(data_file, 'r') as f:
            data = json.load(f)
            self.colleges = [self._flatten(c) for c in data.get('colleges', [])]

    @staticmethod
    def _flatten(college: Dict[str, Any]) -> Dict[str, Any]:
        """Project the nested colleges_enhanced.json schema onto the flat keys
        the ranking code expects. Non-destructive: nested keys are kept.

        Handles the Phase-1 (Scorecard) schema where sat_scores / act_scores /
        gpa fields may be null (test-blind schools, no CDS override)."""
        c = dict(college)
        gpa = college.get('gpa') or {}
        sat = college.get('sat_scores') or {}
        act = college.get('act_scores') or {}
        academics = college.get('academics', {})
        cost = college.get('cost', {})
        admissions = college.get('admissions', {})
        profile = college.get('student_profile', {})

        c.setdefault('avg_gpa', gpa.get('average'))          # may be None
        c.setdefault('gpa_25', gpa.get('25th_percentile'))
        c.setdefault('gpa_75', gpa.get('75th_percentile'))
        c.setdefault('gpa_source', gpa.get('_source'))
        c.setdefault('avg_sat', sat.get('average'))          # may be None
        c.setdefault('sat_25', sat.get('25th_percentile'))
        c.setdefault('sat_75', sat.get('75th_percentile'))
        c.setdefault('has_test_data', bool(sat) or bool(act))
        c.setdefault('act_mid', act.get('midpoint'))
        c.setdefault('majors', academics.get('majors', []))
        c.setdefault('program_mix', academics.get('program_mix', {}))
        c.setdefault('stem_strength', academics.get('stem_strength', False))
        c.setdefault('research_focus', academics.get('research_focus', False))
        c.setdefault('meets_full_need', cost.get('meets_full_need', False))
        c.setdefault('net_price_by_income', cost.get('net_price_by_income', {}))
        c.setdefault('total_cost', cost.get('total_cost_of_attendance'))
        c.setdefault('essays_required', admissions.get('essays_required'))
        c.setdefault('application_deadline',
                     admissions.get('application_deadline') or college.get('application_deadline'))
        c.setdefault('test_optional', admissions.get('test_optional', not bool(sat)))
        # first_gen_support: explicit top-level bool in Phase-1 schema, else derive
        c.setdefault('first_gen_support',
                     college.get('first_gen_support',
                                 (profile.get('first_gen_percent') or 0) >= 0.10))
        c.setdefault('pell_percent', profile.get('pell_grant_percent'))
        return c
    
    def get_college(self, college_id: str) -> Optional[Dict[str, Any]]:
        """Get college by ID"""
        for college in self.colleges:
            if college.get('id') == college_id.lower():
                return college
        return None
    
    def search_colleges(self, 
                       major: Optional[str] = None,
                       location: Optional[str] = None,
                       max_acceptance_rate: float = 1.0,
                       financial_aid_needed: bool = False,
                       selectivity: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Enhanced search with more filters
        
        Args:
            major: Desired major
            location: Location preference (state or region)
            max_acceptance_rate: Maximum acceptance rate (0-1)
            financial_aid_needed: Filter for full-need schools
            selectivity: "most", "highly", "selective", "moderately", "less"
        """
        results = []
        
        for college in self.colleges:
            # Acceptance rate filter
            if college.get('acceptance_rate', 0) > max_acceptance_rate:
                continue
            
            # Major filter
            if major and major.lower() not in [m.lower() for m in college.get('majors', [])]:
                continue
            
            # Location filter
            if location:
                if location.upper() != college.get('state', '') and \
                   location.lower() != college.get('region', '').lower():
                    continue
            
            # Financial aid filter
            if financial_aid_needed and not college.get('meets_full_need', False):
                continue
            
            # Selectivity filter (if tier data available)
            if selectivity:
                college_tier = self._get_selectivity_tier(college)
                if selectivity.lower() not in college_tier.lower():
                    continue
            
            results.append(college)
        
        return results
    
    def _get_selectivity_tier(self, college: Dict[str, Any]) -> str:
        """Determine selectivity tier from acceptance rate"""
        acceptance_rate = college.get('acceptance_rate', 0.5)

        if acceptance_rate < 0.10:
            return "Most Selective"
        elif acceptance_rate < 0.20:
            return "Highly Selective"
        elif acceptance_rate < 0.40:
            return "Selective"
        elif acceptance_rate < 0.60:
            return "Moderately Selective"
        else:
            return "Less Selective"

    def shortlist(self,
                  major: Optional[str] = None,
                  state_pref: Optional[str] = None,
                  region_pref: Optional[str] = None,
                  needs_financial_aid: bool = False,
                  income_band: Optional[str] = None,
                  max_net_price: Optional[int] = None,
                  limit: int = 40) -> List[Dict[str, Any]]:
        """Stage A candidate generation: reduce the full pool to a relevant,
        affordable subset before the ranker scores it. Lenient filters."""
        pool = []
        for c in self.colleges:
            if c.get('acceptance_rate') is None:
                continue
            if major and c.get('majors') and not _offers_major(c, major):
                continue
            if state_pref and (c.get('state') or '').upper() != state_pref.upper():
                continue
            if region_pref and (c.get('region') or '').lower() != region_pref.lower():
                continue
            if needs_financial_aid and max_net_price is not None:
                np = _net_price_for(c, income_band)
                # keep if affordable OR meets full need OR we have no price data
                if np is not None and np > max_net_price and not c.get('meets_full_need'):
                    continue
            pool.append(c)

        # spread across the selectivity range so the ranker can find safeties:
        # sort by acceptance rate, then interleave selective / mid / high-admit.
        pool.sort(key=lambda c: c['acceptance_rate'])
        if len(pool) <= limit:
            return pool
        selective = [c for c in pool if c['acceptance_rate'] < 0.25]
        mid = [c for c in pool if 0.25 <= c['acceptance_rate'] < 0.6]
        high = [c for c in pool if c['acceptance_rate'] >= 0.6]
        take = (selective[: limit // 3] + mid[: limit // 3]
                + high[: limit - 2 * (limit // 3)])
        # backfill if a tier was thin
        if len(take) < limit:
            seen = {id(c) for c in take}
            take += [c for c in pool if id(c) not in seen][: limit - len(take)]
        return take[:limit]

# Global database
db = EnhancedCollegeDatabase()

# ============================================================================
# ENHANCED RANKING WITH STATISTICAL ANALYSIS
# ============================================================================

# --- major label <-> Scorecard CIP family (subset; mirrors scripts/scorecard_lookups) ---
_MAJOR_TO_FAMILY = {
    "computer science": "computer", "engineering": "engineering",
    "mathematics": "mathematics", "biology": "biological", "pre-med": "biological",
    "physics": "physical_science", "chemistry": "physical_science",
    "nursing": "health", "business": "business_marketing",
    "economics": "social_science", "political science": "social_science",
    "sociology": "social_science", "psychology": "psychology", "art": "visual_performing",
    "english": "english", "history": "history", "education": "education",
    "communications": "communication", "journalism": "communication",
    "social work": "public_administration_social_service",
    "criminal justice": "security_law_enforcement", "pre-law": "legal",
    "philosophy": "philosophy_religious", "liberal arts": "multidiscipline",
}
_MAJOR_SYNONYMS = {
    "pre-med": ["biology", "chemistry", "pre-med"],
    "pre-law": ["political science", "history", "philosophy", "pre-law"],
    "economics": ["economics", "business"],
    "computer science": ["computer science", "mathematics"],
    "nursing": ["nursing", "biology"],
    "journalism": ["journalism", "communications", "english"],
}
_INCOME_BANDS = ["0-30000", "30001-48000", "48001-75000", "75001-110000", "110001-plus"]

_CATEGORY_TABLE = {
    (2, 0): "reach",  (2, 1): "target", (2, 2): "safety", (2, 3): "safety",
    (1, 0): "reach",  (1, 1): "reach",  (1, 2): "target", (1, 3): "safety",
    (0, 0): "reach",  (0, 1): "reach",  (0, 2): "reach",  (0, 3): "target",
}


def _offers_major(college: Dict[str, Any], major: Optional[str]) -> bool:
    if not major:
        return True
    labels = [m.lower() for m in (college.get("majors") or [])]
    if not labels:
        return True  # no program data -> don't filter it out
    ml = major.lower().strip()
    if ml in labels:
        return True
    return any(syn in labels for syn in _MAJOR_SYNONYMS.get(ml, []))


def _major_share(college: Dict[str, Any], major: Optional[str]) -> Optional[float]:
    fam = _MAJOR_TO_FAMILY.get((major or "").lower().strip())
    if not fam:
        return None
    return (college.get("program_mix") or {}).get(fam)


def _net_price_for(college: Dict[str, Any], income_band: Optional[str]) -> Optional[int]:
    npi = college.get("net_price_by_income") or {}
    if not npi:
        return None
    if income_band and income_band in npi:
        return npi[income_band]
    lows = [npi[b] for b in ("0-30000", "30001-48000") if b in npi]
    if lows:
        return sum(lows) // len(lows)
    return min(npi.values())


def _expected_gpa(admit_rate: float) -> float:
    if admit_rate < 0.10:
        return 3.92
    if admit_rate < 0.20:
        return 3.85
    if admit_rate < 0.35:
        return 3.72
    if admit_rate < 0.55:
        return 3.55
    return 3.35


def _academic_position(college: Dict[str, Any], gpa: Optional[float],
                       sat: Optional[int]):
    """Return ("above"|"middle"|"below"|"unknown", [notes])."""
    signals, notes = [], []
    g25, g75, gavg = college.get("gpa_25"), college.get("gpa_75"), college.get("avg_gpa")
    if gpa:
        if g25 and g75:
            signals.append(2 if gpa >= g75 else 0 if gpa < g25 else 1)
            notes.append(f"GPA {gpa} vs school's {g25}-{g75} middle 50%")
        elif gavg:
            signals.append(2 if gpa >= gavg + 0.06 else 0 if gpa < gavg - 0.12 else 1)
            notes.append(f"GPA {gpa} vs school avg {gavg}")
    s25, s75, savg = college.get("sat_25"), college.get("sat_75"), college.get("avg_sat")
    if sat and (s25 or savg):
        if s25 and s75:
            signals.append(2 if sat >= s75 else 0 if sat < s25 else 1)
            notes.append(f"SAT {sat} vs school's {s25}-{s75} middle 50%")
        elif savg:
            signals.append(2 if sat >= savg + 70 else 0 if sat < savg - 90 else 1)
            notes.append(f"SAT {sat} vs school avg {savg}")
    if not signals and gpa:
        exp = _expected_gpa(college.get("acceptance_rate", 0.5))
        signals.append(2 if gpa >= exp + 0.05 else 0 if gpa < exp - 0.15 else 1)
        notes.append(f"GPA {gpa} vs ~{exp} typical at this selectivity (school publishes no stats)")
    if not signals:
        return "unknown", ["no GPA or test scores available to position the student"]
    mean = sum(signals) / len(signals)
    pos = "above" if mean >= 1.7 else "below" if mean < 0.8 else "middle"
    return pos, notes


def categorize(college: Dict[str, Any], gpa: Optional[float], sat: Optional[int]):
    """Return (category, est_admit_prob, position, notes).

    Category = academic position x published admit-rate band (transparent table).
    Everyone is a reach at sub-10%% schools regardless of stats."""
    pos, notes = _academic_position(college, gpa, sat)
    ar = college.get("acceptance_rate", 0.5)
    band = 0 if ar < 0.10 else 1 if ar < 0.25 else 2 if ar < 0.50 else 3
    pi = {"above": 2, "middle": 1, "below": 0, "unknown": 1}[pos]
    category = _CATEGORY_TABLE[(pi, band)]
    mult = {2: 2.5, 1: 1.0, 0: 0.4}[pi]
    est = min(0.90, max(0.03, ar * mult))
    return category, est, pos, notes


def _strategy_tips(admit_rate: float, major: Optional[str],
                   college: Dict[str, Any]) -> List[str]:
    tips = []
    if admit_rate < 0.10:
        tips.append("Essays and activities decide it here - strong stats are the floor, not the case")
    elif admit_rate < 0.20:
        tips.append("Show specific, concrete interest in this school's programs")
    if college.get("test_optional"):
        tips.append("Test-optional / test-blind - a strong transcript and rigor carry more weight")
    if major and _offers_major(college, major) and (college.get("majors")):
        tips.append(f"Highlight coursework or projects related to {major}")
    return tips


def _match_score(college: Dict[str, Any], major: Optional[str], is_first_gen: bool,
                 needs_aid: bool, income_band: Optional[str]):
    """0-100 "how good a match for YOU" (separate from admit likelihood)."""
    score, reasoning, guidance = 0.0, [], []

    # major fit (0-35)
    if major:
        labels = [m.lower() for m in (college.get("majors") or [])]
        if not labels:
            score += 15
        elif major.lower() in labels:
            share = _major_share(college, major)
            if share and share >= 0.08:
                score += 35
                reasoning.append(f"{major} is a major program here (~{share*100:.0f}% of degrees)")
            else:
                score += 25
                reasoning.append(f"{major} is offered here")
        elif _offers_major(college, major):
            score += 19
            reasoning.append(f"{major} available via a related department")
        else:
            score += 3
            reasoning.append(f"{major} not clearly offered - verify in the catalog")
    else:
        score += 18

    # affordability (0-35)
    if needs_aid:
        np = _net_price_for(college, income_band)
        if college.get("meets_full_need"):
            score += 35
            reasoning.append("commits to meet 100% of demonstrated financial need")
            guidance.append("File FAFSA + CSS Profile early - full need is met")
        elif np is not None:
            if np <= 8000:
                score += 33
            elif np <= 16000:
                score += 24
            elif np <= 25000:
                score += 14
            else:
                score += 4
            reasoning.append(f"estimated net price ~${np:,}/yr at your income level")
        else:
            score += 12
            reasoning.append("no net-price data - run the school's net price calculator")
    else:
        score += 20

    # first-gen support (0-15)
    if is_first_gen:
        if college.get("first_gen_support"):
            score += 15
            pct = (college.get("student_profile") or {}).get("first_gen_percent")
            reasoning.append(
                f"sizable first-gen community" + (f" ({pct*100:.0f}%)" if pct else ""))
            guidance.append("Ask about first-gen mentorship / summer bridge programs")
        else:
            score += 4
    else:
        score += 8

    # outcomes (0-15)
    grad = (college.get("student_profile") or {}).get("graduation_rate")
    if grad:
        score += 12 if grad >= 0.85 else 8 if grad >= 0.65 else 3
        reasoning.append(f"4-year graduation rate {grad*100:.0f}%")
    else:
        score += 6

    return min(100.0, score), reasoning, guidance


def analyze_college_fit_enhanced(college_id: str,
                                 student_gpa: Optional[float],
                                 student_sat: Optional[int],
                                 student_major: Optional[str] = None,
                                 is_first_gen: bool = False,
                                 needs_financial_aid: bool = False,
                                 income_band: Optional[str] = None) -> CollegeFitAnalysis:
    """Fit analysis: match_score (fit FOR the student) + category (admit LIKELIHOOD),
    computed separately. Uses real Scorecard/CDS percentiles when present, an
    admit-rate-derived expectation otherwise."""
    college = db.get_college(college_id)
    if not college:
        raise ValueError(f"College '{college_id}' not found")

    gpa = float(student_gpa) if student_gpa else None
    sat = int(student_sat) if student_sat else None

    match, reasoning, guidance = _match_score(
        college, student_major, is_first_gen, needs_financial_aid, income_band)
    category, est_prob, position, pos_notes = categorize(college, gpa, sat)

    ar = college.get("acceptance_rate", 0.5)
    reasoning = pos_notes + reasoning
    reasoning.append({
        "above": "stats sit above this school's middle 50%",
        "middle": "stats sit within this school's middle 50%",
        "below": "stats sit below this school's middle 50%",
        "unknown": "not enough stats to position the student",
    }[position])
    if ar < 0.10:
        reasoning.append(f"{ar*100:.0f}% admit rate - a reach for every applicant, strong stats included")
    guidance += _strategy_tips(ar, student_major, college)

    np = _net_price_for(college, income_band)
    context = {
        "selectivity_tier": db._get_selectivity_tier(college),
        "acceptance_rate": f"{ar*100:.1f}%",
        "academic_position": position,
        "est_admit_probability": f"~{est_prob*100:.0f}% (rough estimate, not a prediction)",
        "net_price_estimate": (f"${np:,}/yr at low income" if np is not None else "no data"),
        "meets_full_need": bool(college.get("meets_full_need")),
        "first_gen_support": bool(college.get("first_gen_support")),
        "major_available": _offers_major(college, student_major) if student_major else None,
        "test_optional": bool(college.get("test_optional")),
        "application_deadline": college.get("application_deadline"),
        "data_source": (college.get("gpa_source") or "scorecard"),
    }

    return CollegeFitAnalysis(
        college_name=college.get("name"),
        fit_score=round(match, 1),
        category=category,
        confidence=est_prob,
        gpa_fit=0.0, sat_fit=0.0, major_fit=0.0,
        selectivity_adjustment=1.0, support_fit=0.0,
        reasoning=reasoning,
        guidance_tips=guidance,
        context=context,
    )

# ============================================================================
# RAG-ENABLED RETRIEVAL OF COLLEGE GUIDANCE
# ============================================================================

def retrieve_college_guidance(college_id: str, 
                             student_major: Optional[str] = None,
                             is_first_gen: bool = False) -> Dict[str, Any]:
    """
    Retrieve contextual guidance about a college
    (This would use ChromaDB RAG in full implementation)
    
    For now, returns college-specific guidance based on data
    """
    
    college = db.get_college(college_id)
    if not college:
        return {"error": f"College '{college_id}' not found"}
    
    guidance = {
        "college_name": college.get('name'),
        "description": college.get('description', ''),
        "academic_profile": [],
        "application_tips": [],
        "student_life": [],
        "financial_guidance": [],
        "community_fit": [],
    }
    
    # Academic profile
    if college.get('stem_strength'):
        guidance["academic_profile"].append("Strong STEM programs, especially engineering and computer science")
    if college.get('research_focus'):
        guidance["academic_profile"].append("Research-focused institution - undergraduate research opportunities available")
    
    # Application tips
    acceptance_rate = college.get('acceptance_rate', 0.5)
    if acceptance_rate < 0.10:
        guidance["application_tips"].append("Extremely selective - ensure all components are strong")
        guidance["application_tips"].append("Essays must show personal narrative and authentic passion")
    elif acceptance_rate < 0.20:
        guidance["application_tips"].append("Highly selective - demonstrate specific interest in the institution")
    
    essays_required = college.get('essays_required') or 0
    if essays_required > 0:
        guidance["application_tips"].append(f"Requires {essays_required} supplemental essay(s) - invest significant time")

    deadline = college.get('application_deadline')
    if deadline:
        guidance["application_tips"].append(f"Regular Decision deadline: {deadline}")
    if college.get('test_optional'):
        guidance["application_tips"].append("Test-optional / test-blind - transcript rigor matters most")
    
    # Financial guidance
    if college.get('meets_full_need'):
        guidance["financial_guidance"].append("Meets 100% of demonstrated financial need - no loans in aid packages")
    
    if is_first_gen and college.get('first_gen_support'):
        guidance["financial_guidance"].append("First-generation students: Special scholarship programs available")
        guidance["community_fit"].append("Active first-gen student community and mentorship programs")
    
    # Student life
    if college.get('size') == 'small':
        guidance["student_life"].append("Small undergraduate population - close-knit community")
    elif college.get('size') == 'large':
        guidance["student_life"].append("Large university - diverse opportunities but more independent")
    
    if college.get('setting') == 'urban':
        guidance["student_life"].append("Urban location - vibrant city culture and internship opportunities")
    elif college.get('setting') == 'suburban':
        guidance["student_life"].append("Suburban setting - campus-focused community")
    
    return guidance

# ============================================================================
# TOOL EXPORTS
# ============================================================================

def search_colleges(major: Optional[str] = None,
                   location: Optional[str] = None,
                   max_acceptance_rate: float = 1.0,
                   financial_aid_needed: bool = False) -> Dict[str, Any]:
    """Search tool interface (backward compatible)"""
    
    results = db.search_colleges(
        major=major,
        location=location,
        max_acceptance_rate=max_acceptance_rate,
        financial_aid_needed=financial_aid_needed
    )
    
    formatted = []
    for college in results[:15]:
        formatted.append({
            "name": college.get('name'),
            "id": college.get('id'),
            "acceptance_rate": f"{college.get('acceptance_rate', 0)*100:.1f}%",
            "avg_gpa": college.get('avg_gpa'),
            "avg_sat": college.get('avg_sat'),
            "location": college.get('location'),
            "major_offered": major in college.get('majors', []) if major else None
        })
    
    return {
        "query": {
            "major": major,
            "location": location,
            "max_acceptance_rate": f"{max_acceptance_rate*100:.0f}%",
            "financial_aid_required": financial_aid_needed
        },
        "results_count": len(results),
        "colleges": formatted
    }

def rank_college_fit(college_id: str,
                    student_gpa: Optional[float],
                    student_sat: Optional[int],
                    student_major: Optional[str] = None,
                    is_first_gen: bool = False,
                    needs_financial_aid: bool = False,
                    income_band: Optional[str] = None) -> Dict[str, Any]:
    """Ranking tool interface (enhanced)"""

    analysis = analyze_college_fit_enhanced(
        college_id=college_id,
        student_gpa=student_gpa,
        student_sat=student_sat,
        student_major=student_major,
        is_first_gen=is_first_gen,
        needs_financial_aid=needs_financial_aid,
        income_band=income_band,
    )

    return {
        "college": analysis.college_name,
        "fit_score": round(analysis.fit_score, 1),
        "category": analysis.category,
        "confidence": f"{analysis.confidence*100:.0f}%",
        "reasoning": analysis.reasoning,
        "guidance_tips": analysis.guidance_tips,
        "context": analysis.context,
    }

def get_college_guidance(college_id: str,
                        student_major: Optional[str] = None,
                        is_first_gen: bool = False) -> Dict[str, Any]:
    """Retrieve college guidance context"""
    return retrieve_college_guidance(
        college_id=college_id,
        student_major=student_major,
        is_first_gen=is_first_gen
    )

# Tool registry (for agent)
ENHANCED_TOOLS = {
    "search_colleges": search_colleges,
    "rank_college_fit": rank_college_fit,
    "get_college_guidance": get_college_guidance,
}
