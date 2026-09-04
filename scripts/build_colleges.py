#!/usr/bin/env python3
"""
Phase 1 ETL: build colleges_enhanced.json from the College Scorecard API.

Pulls ~COLLEGE_POOL_SIZE degree-granting 4-year institutions spanning the
selectivity range (with a guaranteed block of high-admit "safety" schools),
projects them onto the schema the Discovery ranker reads, merges hand-curated
overrides (real GPA percentiles, deadlines, meets-full-need), and writes the
file with a _meta / _provenance trail.

Usage:
    SCORECARD_API_KEY=xxxx  python scripts/build_colleges.py
    python scripts/build_colleges.py --dry-run      # fetch + summarize, don't write
    python scripts/build_colleges.py --limit 60     # small build for testing

Scorecard gives admit rate, SAT/ACT, net price by income, size, Pell / first-gen
share, completion, and major mix. It does NOT provide GPA, deadlines, essay
counts, or a meets-full-need flag - those come from data/college_overrides.json
or are left null.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import (  # noqa: E402
    COLLEGE_DATA_FILE, COLLEGE_POOL_SIZE, SCORECARD_API_KEY, SCORECARD_BASE,
)
from scripts.scorecard_lookups import (  # noqa: E402
    CIP_FAMILY_TO_MAJORS, INCOME_BANDS, OWNERSHIP, is_research,
    majors_from_program_mix, region_of, setting_of, size_bucket, stem_strength,
)

OVERRIDES_FILE = Path(__file__).resolve().parent.parent / "data" / "college_overrides.json"

# legacy slugs that other files (essay_examples.json, college_repo aliases) depend on
LEGACY_SLUGS = {
    "Stanford University": "stanford",
    "California Institute of Technology": "caltech",
    "University of California-Berkeley": "berkeley",
    "University of Washington-Seattle Campus": "uw",
    "The University of Texas at Austin": "ut-austin",
    "University of Illinois Urbana-Champaign": "uiuc",
}

_SLUG_STOP = {"university", "the", "of", "at", "main", "campus", "a", "and"}

# Scorecard program_percentage families we pull (leaf fields)
_PROGRAM_FAMILIES = list(CIP_FAMILY_TO_MAJORS)

_SAT_LEAVES = [
    "sat_scores.average.overall",
    "sat_scores.25th_percentile.math", "sat_scores.75th_percentile.math",
    "sat_scores.25th_percentile.critical_reading", "sat_scores.75th_percentile.critical_reading",
    "sat_scores.midpoint.math", "sat_scores.midpoint.critical_reading",
]

FIELDS = ",".join(
    ["id", "school.name", "school.city", "school.state", "school.locale",
     "school.ownership", "school.carnegie_basic",
     "latest.admissions.admission_rate.overall",
     "latest.admissions.act_scores.midpoint.cumulative",
     "latest.cost.attendance.academic_year",
     "latest.student.size",
     "latest.student.demographics.first_generation",
     "latest.aid.pell_grant_rate",
     "latest.completion.completion_rate_4yr_150nt"]
    + [f"latest.admissions.{leaf}" for leaf in _SAT_LEAVES]
    + [f"2020.admissions.{leaf}" for leaf in _SAT_LEAVES]
    + [f"latest.academics.program_percentage.{f}" for f in _PROGRAM_FAMILIES]
    + [f"latest.cost.net_price.public.by_income_level.{b}" for b in INCOME_BANDS]
    + [f"latest.cost.net_price.private.by_income_level.{b}" for b in INCOME_BANDS]
)

# (label, extra query params, pages) - kept small to respect DEMO_KEY limits
QUERIES = [
    ("large 4-yr", {"latest.student.size__range": "2000..120000",
                    "latest.admissions.admission_rate.overall__range": "0..1",
                    "sort": "latest.student.size:desc"}, 3),
    ("selective LACs", {"latest.student.size__range": "400..2000",
                        "latest.admissions.admission_rate.overall__range": "0..0.45",
                        "sort": "latest.admissions.admission_rate.overall:asc"}, 1),
    ("high-admit safeties", {"latest.student.size__range": "2500..120000",
                             "latest.admissions.admission_rate.overall__range": "0.68..1",
                             "sort": "latest.student.size:desc"}, 1),
]


def _get(params: Dict[str, Any]) -> Dict[str, Any]:
    p = {"api_key": SCORECARD_API_KEY, "fields": FIELDS, "per_page": 100,
         "school.degrees_awarded.predominant": 3, "school.operating": 1,
         "school.ownership__range": "1..2", **params}
    for attempt in range(4):
        r = requests.get(SCORECARD_BASE, params=p, timeout=40)
        if r.status_code == 200:
            return r.json()
        if r.status_code == 429:
            wait = 20 * (attempt + 1)
            print(f"  429 rate-limited; sleeping {wait}s", file=sys.stderr)
            time.sleep(wait)
            continue
        r.raise_for_status()
    raise RuntimeError("Scorecard API: repeated 429s - use a real api.data.gov key")


def _slugify(name: str, taken: set) -> str:
    if name in LEGACY_SLUGS:
        return LEGACY_SLUGS[name]
    s = name.replace("&", " and ")
    s = re.sub(r"[.,'\-/()]", " ", s).lower()
    words = [w for w in s.split() if w not in _SLUG_STOP]
    slug = "-".join(words[:5]) or re.sub(r"\W+", "-", name.lower())
    slug = slug.strip("-")[:48]
    base, n = slug, 2
    while slug in taken:
        slug = f"{base}-{n}"
        n += 1
    return slug


def _f(v: Any) -> Optional[float]:
    try:
        return round(float(v), 4) if v is not None else None
    except (TypeError, ValueError):
        return None


def _sat_block(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Combined SAT (math + reading) from latest, falling back to 2020."""
    for yr in ("latest", "2020"):
        pfx = f"{yr}.admissions."
        m25, r25 = row.get(pfx + "sat_scores.25th_percentile.math"), row.get(pfx + "sat_scores.25th_percentile.critical_reading")
        m75, r75 = row.get(pfx + "sat_scores.75th_percentile.math"), row.get(pfx + "sat_scores.75th_percentile.critical_reading")
        avg = row.get(pfx + "sat_scores.average.overall")
        mmid, rmid = row.get(pfx + "sat_scores.midpoint.math"), row.get(pfx + "sat_scores.midpoint.critical_reading")
        p25 = (m25 + r25) if (m25 and r25) else None
        p75 = (m75 + r75) if (m75 and r75) else None
        average = avg or ((mmid + rmid) if (mmid and rmid) else None)
        if p25 or p75 or average:
            return {
                "average": int(average) if average else None,
                "25th_percentile": int(p25) if p25 else None,
                "75th_percentile": int(p75) if p75 else None,
                "_source": f"scorecard:{yr}",
            }
    return None


def _net_price(row: Dict[str, Any], ownership: int) -> Dict[str, Any]:
    kind = "public" if ownership == 1 else "private"
    by_income = {}
    for b in INCOME_BANDS:
        v = row.get(f"latest.cost.net_price.{kind}.by_income_level.{b}")
        if v is not None:
            by_income[b] = int(v)
    return by_income


def transform(row: Dict[str, Any], taken: set) -> Optional[Dict[str, Any]]:
    name = row.get("school.name")
    admit = _f(row.get("latest.admissions.admission_rate.overall"))
    if not name or admit is None:
        return None
    ownership = row.get("school.ownership") or 2
    state = row.get("school.state")
    size = row.get("latest.student.size")
    slug = _slugify(name, taken)
    taken.add(slug)

    program_mix = {
        f: _f(row.get(f"latest.academics.program_percentage.{f}"))
        for f in _PROGRAM_FAMILIES
        if row.get(f"latest.academics.program_percentage.{f}")
    }
    majors = majors_from_program_mix(program_mix)
    act_mid = row.get("latest.admissions.act_scores.midpoint.cumulative")
    sat = _sat_block(row)
    fg = _f(row.get("latest.student.demographics.first_generation"))
    coa = row.get("latest.cost.attendance.academic_year")

    return {
        "id": slug,
        "scorecard_id": row.get("id"),
        "name": name,
        "location": f"{row.get('school.city', '')}, {state}".strip(", "),
        "state": state,
        "region": region_of(state),
        "description": (
            f"{OWNERSHIP.get(ownership, 'college').capitalize()} institution in "
            f"{state}. Scorecard admit rate {admit * 100:.0f}%."
        ),
        "acceptance_rate": admit,
        "acceptance_rate_note": "College Scorecard, latest reporting year",
        "gpa": {"average": None, "25th_percentile": None, "75th_percentile": None,
                "_source": None},
        "sat_scores": ({**sat, "optional": sat["_source"] != "scorecard:latest"}
                       if sat else None),
        "act_scores": ({"midpoint": int(act_mid), "_source": "scorecard:latest"}
                       if act_mid else None),
        "cost": {
            "total_cost_of_attendance": int(coa) if coa else None,
            "meets_full_need": False,
            "net_price_by_income": _net_price(row, ownership),
            "_source": "scorecard:latest",
        },
        "academics": {
            "majors": majors,
            "program_mix": {k: v for k, v in sorted(program_mix.items(),
                                                    key=lambda kv: -(kv[1] or 0))[:8]},
            "stem_strength": stem_strength(program_mix),
            "research_focus": is_research(row.get("school.carnegie_basic"), size),
        },
        "student_profile": {
            "undergraduate_population": int(size) if size else None,
            "first_gen_percent": fg,
            "pell_grant_percent": _f(row.get("latest.aid.pell_grant_rate")),
            "graduation_rate": _f(row.get("latest.completion.completion_rate_4yr_150nt")),
        },
        "admissions": {
            "essays_required": None,
            "application_deadline": None,
            "financial_aid_deadline": None,
            "test_optional": sat is None or sat["_source"] != "scorecard:latest",
        },
        "first_gen_support": bool(fg and fg >= 0.15),
        "size": size_bucket(size),
        "setting": setting_of(row.get("school.locale")),
        "_provenance": {
            "scorecard_id": row.get("id"),
            "test_data_year": sat["_source"].split(":")[1] if sat else None,
            "gpa_source": None,
        },
    }


def _deep_merge(base: Dict[str, Any], over: Dict[str, Any]) -> None:
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v


def apply_overrides(colleges: List[Dict[str, Any]]) -> int:
    if not OVERRIDES_FILE.exists():
        return 0
    overrides = json.loads(OVERRIDES_FILE.read_text())
    by_slug = {c["id"]: c for c in colleges}
    n, unmatched = 0, []
    for slug, patch in overrides.items():
        if slug.startswith("_"):
            continue
        c = by_slug.get(slug)
        if not c:
            unmatched.append(slug)
            continue
        _deep_merge(c, patch)
        if patch.get("gpa"):
            c["gpa"]["_source"] = "cds_override"
            c["_provenance"]["gpa_source"] = "cds_override"
        n += 1
    if unmatched:
        print(f"  overrides: {len(unmatched)} keys did not match a slug: "
              f"{', '.join(unmatched[:20])}", file=sys.stderr)
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=COLLEGE_POOL_SIZE)
    args = ap.parse_args()

    if SCORECARD_API_KEY == "DEMO_KEY":
        print("WARNING: using DEMO_KEY - will likely rate-limit. "
              "Set SCORECARD_API_KEY.", file=sys.stderr)

    raw: Dict[int, Dict[str, Any]] = {}
    for label, params, pages in QUERIES:
        for page in range(pages):
            data = _get({**params, "page": page})
            hits = data.get("results", [])
            for row in hits:
                raw.setdefault(row["id"], row)
            print(f"  {label} p{page}: +{len(hits)} (pool {len(raw)})")
            time.sleep(1.0)

    taken: set = set()
    colleges: List[Dict[str, Any]] = []
    for row in raw.values():
        rec = transform(row, taken)
        if rec:
            colleges.append(rec)

    # trim to limit but keep every high-admit school (safeties) up to 70
    safeties = [c for c in colleges if c["acceptance_rate"] >= 0.65]
    others = [c for c in colleges if c["acceptance_rate"] < 0.65]
    others.sort(key=lambda c: (c["sat_scores"] is None, c["acceptance_rate"]))
    keep = safeties[:70] + others
    keep.sort(key=lambda c: c["acceptance_rate"])
    colleges = keep[:args.limit]

    n_over = apply_overrides(colleges)

    out = {
        "_meta": {
            "generated": time.strftime("%Y-%m-%d"),
            "source": "College Scorecard API (api.data.gov)",
            "school_count": len(colleges),
            "overrides_applied": n_over,
            "notes": "GPA / deadlines / essay counts / meets_full_need come from "
                     "data/college_overrides.json where present, else null. "
                     "SAT combined = math + reading percentiles.",
        },
        "colleges": sorted(colleges, key=lambda c: c["name"]),
    }

    n_sat = sum(1 for c in colleges if c["sat_scores"])
    n_safe = sum(1 for c in colleges if c["acceptance_rate"] >= 0.65)
    n_afford = sum(1 for c in colleges if c["cost"]["net_price_by_income"])
    print(f"\n{len(colleges)} schools | SAT data: {n_sat} | safeties (>=65%): "
          f"{n_safe} | net-price data: {n_afford} | overrides: {n_over}")

    if args.dry_run:
        print("--dry-run: not writing")
        return
    COLLEGE_DATA_FILE.write_text(json.dumps(out, indent=2))
    print(f"wrote {COLLEGE_DATA_FILE}")


if __name__ == "__main__":
    main()
