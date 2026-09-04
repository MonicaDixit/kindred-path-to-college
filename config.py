"""
Configuration for Kindred College Advisor Agent
"""

import os
from pathlib import Path

# Load .env if python-dotenv is available (keeps OPENROUTER_API_KEY out of code)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except Exception:
    pass

# ============================================================================
# PROJECT PATHS
# ============================================================================
PROJECT_ROOT = Path(__file__).parent
COLLEGE_DATA_FILE = PROJECT_ROOT / "colleges_enhanced.json"
CASE_STUDIES_FILE = PROJECT_ROOT / "case_studies_from_real_sources.json"
ESSAY_EXAMPLES_FILE = PROJECT_ROOT / "essay_examples.json"
ESSAY_METHODOLOGY_FILE = PROJECT_ROOT / "essay_methodology.json"

# ============================================================================
# LLM CONFIGURATION
# ============================================================================
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "sk-or-v1-YOUR-KEY-HERE")
LLM_MODEL = os.getenv("LLM_MODEL", "minimax/minimax-m3:free")

# Free OpenRouter models are often slow / briefly overloaded. Retry a few times
# and, on repeated failure, fall through to a second model.
LLM_FALLBACK_MODEL = os.getenv("LLM_FALLBACK_MODEL", "openrouter/free")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "60"))        # read timeout, then fail over
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))

# The default model is a *reasoning* model: it spends 600-900 hidden tokens
# "thinking" before every answer, which on a slow free tier adds 15-40s per call
# for zero benefit on these format-the-data tasks. Turn that off unless overridden.
LLM_DISABLE_REASONING = os.getenv("LLM_DISABLE_REASONING", "true").lower() == "true"

# ============================================================================
# MULTI-AGENT SETTINGS (LangGraph architecture)
# ============================================================================
# Fallback candidate set (used only if the college DB failed to load / is tiny).
# The Discovery agent normally builds its own shortlist from the full pool.
CANDIDATE_COLLEGES = ["stanford", "berkeley", "caltech", "uw", "ut-austin", "uiuc"]

# ============================================================================
# COLLEGE DATA PIPELINE (Phase 1: College Scorecard ETL)
# ============================================================================
# api.data.gov key for the College Scorecard API. DEMO_KEY works for the small
# number of calls the build script makes (get a free key to lift the rate limit).
SCORECARD_API_KEY = os.getenv("SCORECARD_API_KEY", "DEMO_KEY")
SCORECARD_BASE = "https://api.data.gov/ed/collegescorecard/v1/schools"
# Target number of schools in colleges_enhanced.json.
COLLEGE_POOL_SIZE = int(os.getenv("COLLEGE_POOL_SIZE", "350"))
# How many shortlisted schools the Discovery ranker scores per list request.
DISCOVERY_SHORTLIST_SIZE = int(os.getenv("DISCOVERY_SHORTLIST_SIZE", "40"))
# Net price ceiling (per year) applied as an affordability filter when the
# student needs financial aid.
NET_PRICE_CEILING = int(os.getenv("NET_PRICE_CEILING", "25000"))

# ============================================================================
# AGENT SETTINGS
# ============================================================================
VERBOSE_MODE = True
MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "1000"))   # visible answer budget
TEMPERATURE = 0.7

# ============================================================================
# DEMO STUDENT
# ============================================================================
DEMO_STUDENT = {
    "name": "Alex Chen",
    "gpa": 3.85,
    "sat_score": 1520,
    "major": "Computer Science",
    "location": "California",
    "is_first_gen": True,
    "needs_financial_aid": True
}
