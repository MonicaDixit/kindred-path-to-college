"""Phase 1 ranker tests. Run: python scripts/test_phase1_ranker.py

Exercises the split of match-score vs. admit-category, the categorization table,
test-optional degradation, and the affordability shortlist filter - on a small
synthetic fixture so it's independent of the built pool.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import college_tools_enhanced as ct  # noqa: E402

FIXTURE = [
    {  # ultra-selective, full need, has percentiles
        "id": "elite", "name": "Elite U", "state": "MA", "region": "Northeast",
        "acceptance_rate": 0.05,
        "gpa": {"average": 3.95, "25th_percentile": 3.9, "75th_percentile": 4.0},
        "sat_scores": {"average": 1520, "25th_percentile": 1470, "75th_percentile": 1570},
        "act_scores": {"midpoint": 34},
        "cost": {"total_cost_of_attendance": 82000, "meets_full_need": True,
                 "net_price_by_income": {"0-30000": 3000, "48001-75000": 12000}},
        "academics": {"majors": ["Computer Science", "Biology"],
                      "program_mix": {"computer": 0.12}, "stem_strength": True},
        "student_profile": {"first_gen_percent": 0.14, "graduation_rate": 0.96},
        "admissions": {"test_optional": False}, "first_gen_support": False,
        "size": "medium", "setting": "urban",
    },
    {  # mid public, test-optional (no SAT), affordable in-state-ish
        "id": "bigstate", "name": "Big State U", "state": "OH", "region": "Midwest",
        "acceptance_rate": 0.72,
        "gpa": {"average": None, "25th_percentile": None, "75th_percentile": None},
        "sat_scores": None, "act_scores": {"midpoint": 26},
        "cost": {"total_cost_of_attendance": 28000, "meets_full_need": False,
                 "net_price_by_income": {"0-30000": 9000, "48001-75000": 15000}},
        "academics": {"majors": ["Computer Science", "Nursing", "Business"],
                      "program_mix": {"computer": 0.06, "health": 0.1, "business_marketing": 0.2},
                      "stem_strength": False},
        "student_profile": {"first_gen_percent": 0.34, "graduation_rate": 0.62},
        "admissions": {"test_optional": True}, "first_gen_support": True,
        "size": "large", "setting": "suburban",
    },
    {  # selective-ish, pricey for low income, no full need
        "id": "pricey", "name": "Pricey Private", "state": "NY", "region": "Northeast",
        "acceptance_rate": 0.30,
        "gpa": {"average": 3.7, "25th_percentile": 3.5, "75th_percentile": 3.9},
        "sat_scores": {"average": 1380, "25th_percentile": 1300, "75th_percentile": 1460},
        "act_scores": {"midpoint": 31},
        "cost": {"total_cost_of_attendance": 70000, "meets_full_need": False,
                 "net_price_by_income": {"0-30000": 41000, "48001-75000": 45000}},
        "academics": {"majors": ["Business", "Economics", "Psychology"],
                      "program_mix": {"business_marketing": 0.3}, "stem_strength": False},
        "student_profile": {"first_gen_percent": 0.08, "graduation_rate": 0.8},
        "admissions": {"test_optional": True}, "first_gen_support": False,
        "size": "small", "setting": "town",
    },
]

ct.db.colleges = [ct.EnhancedCollegeDatabase._flatten(c) for c in FIXTURE]


def rank(cid, **kw):
    return ct.rank_college_fit(cid, kw.pop("gpa", None), kw.pop("sat", None), **kw)


def main() -> None:
    # 1. strong student: elite is still a reach (sub-10%), big state is a safety
    r = rank("elite", gpa=3.98, sat=1550, student_major="Computer Science")
    assert r["category"] == "reach", r
    assert "reach for every applicant" in " ".join(r["reasoning"]).lower()
    r = rank("bigstate", gpa=3.98, sat=1550, student_major="Computer Science")
    assert r["category"] == "safety", r

    # 2. weak student: nothing is a safety; big state (72%) is a target at best
    r = rank("bigstate", gpa=2.9, sat=None, student_major="Nursing")
    assert r["category"] in ("target", "reach"), r
    assert r["context"]["academic_position"] in ("below", "unknown"), r

    # 3. test-optional school with no SAT -> position from GPA vs derived expectation
    r = rank("bigstate", gpa=3.9, sat=None, student_major="Computer Science")
    assert r["context"]["academic_position"] in ("above", "middle"), r

    # 4. match score: full-need school beats a pricey one for an aid student
    aid = dict(student_major="Business", is_first_gen=True,
               needs_financial_aid=True, income_band="0-30000")
    m_elite = rank("elite", gpa=3.9, sat=1500, **aid)["fit_score"]
    m_pricey = rank("pricey", gpa=3.9, sat=1500, **aid)["fit_score"]
    assert m_elite > m_pricey, (m_elite, m_pricey)

    # 5. shortlist affordability filter drops the pricey (no-full-need, $41k) school
    #    for a low-income student but keeps the full-need and the cheap one
    sl = ct.db.shortlist(needs_financial_aid=True, income_band="0-30000",
                         max_net_price=25000, limit=10)
    ids = {c["id"] for c in sl}
    assert "pricey" not in ids, ids
    assert "bigstate" in ids and "elite" in ids, ids
    # without aid need, no affordability filter
    sl2 = ct.db.shortlist(needs_financial_aid=False, limit=10)
    assert "pricey" in {c["id"] for c in sl2}
    # major filter: elite (no Business dept) is excluded from a Business search
    assert "elite" not in {c["id"] for c in ct.db.shortlist(major="Business", limit=10)}

    # 6. est admit probability is clamped and labelled
    r = rank("elite", gpa=3.5, sat=1200)
    pct = int(r["confidence"].rstrip("%"))
    assert 3 <= pct <= 90, r["confidence"]
    assert "rough estimate" in r["context"]["est_admit_probability"]

    print("phase 1 ranker: all assertions passed")


if __name__ == "__main__":
    main()
