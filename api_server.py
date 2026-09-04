"""
FastAPI backend for kindred-path2college.

Wraps the LangGraph multi-agent system (kindred_graph.GRAPH) and serves the
static resource / college data the React frontend renders.

Run:
    /usr/local/bin/python3 -m uvicorn api_server:app --reload --port 8000
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

import college_repo
import guardrails
from config import COLLEGE_DATA_FILE, PROJECT_ROOT
from kindred_graph import GRAPH
from kindred_state import new_state

app = FastAPI(title="kindred-path2college API", version="1.0.0")

# CORS: local dev origins by default; add production origins with
# FRONTEND_ORIGINS="https://your-frontend.example,https://another" (comma-separated).
_origins = [
    "http://localhost:5173", "http://127.0.0.1:5173",
    "http://localhost:4173", "http://127.0.0.1:4173",
]
_origins += [o.strip() for o in os.getenv("FRONTEND_ORIGINS", "").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Agent metadata (for the frontend chat UI)
# ---------------------------------------------------------------------------

AGENTS = {
    "discovery": {
        "id": "discovery",
        "name": "Discovery Advisor",
        "blurb": "Finds colleges that fit your profile and answers questions about specific schools.",
        "kind": "LLM + retrieval",
        "examples": [
            "I'm pre-med, 3.2 GPA, 1280 SAT, first-gen. Give me colleges.",
            "Tell me about the University of Washington. What's the deadline?",
        ],
    },
    "essay": {
        "id": "essay",
        "name": "Essay Coach",
        "blurb": "Gives specific, encouraging feedback on drafts and helps you find your angle.",
        "kind": "LLM + example essays",
        "examples": [
            "How should I approach the Berkeley leadership essay?",
            "Here's my Stanford essay draft: ...",
        ],
    },
    "planning": {
        "id": "planning",
        "name": "Planning Assistant",
        "blurb": "Turns your college list into a week-by-week timeline. Deterministic, instant, no guesswork.",
        "kind": "Deterministic",
        "examples": [
            "What's my deadline order?",
            "Help me plan my weeks.",
        ],
    },
    "support": {
        "id": "support",
        "name": "Kindred",
        "blurb": "Here for you when the process feels like too much.",
        "kind": "Support",
        "examples": [],
    },
    "respond": {
        "id": "coordinator",
        "name": "Kindred",
        "blurb": "Your guide. Routes you to the right specialist.",
        "kind": "Coordinator",
        "examples": [],
    },
}


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    session_id: str
    message: str
    profile: Optional[Dict[str, Any]] = None  # optional seed from the UI form


class ChatResponse(BaseModel):
    reply: str
    intent: str
    route: str
    agent: Dict[str, Any]
    state: Dict[str, Any]
    guardrail_flags: List[str] = []
    escalated: bool = False
    escalations: List[Dict[str, Any]] = []
    awaiting_resume: bool = False
    human_requested: bool = False


def _config(session_id: str) -> Dict[str, Any]:
    return {"configurable": {"thread_id": session_id}}


def _state_summary(values: Dict[str, Any]) -> Dict[str, Any]:
    """Trim the raw graph state to what the UI shows in its sidebar."""
    if not values:
        return {}
    deadlines = values.get("college_deadlines", {})
    essays = {
        cid: {
            "status": rec.get("status", "not_started"),
            "drafts": len(rec.get("drafts", [])),
        }
        for cid, rec in values.get("essays", {}).items()
    }
    return {
        "profile": values.get("student_profile", {}),
        "selected_colleges": [
            {"id": cid, "name": college_repo.name_of(cid), "deadline": deadlines.get(cid)}
            for cid in values.get("selected_colleges", [])
        ],
        "discussed_colleges": [
            {"id": cid, "name": college_repo.name_of(cid)}
            for cid in values.get("discussed_colleges", [])
        ],
        "essays": essays,
        "essay_coaching": {
            "path": values.get("essay_path", ""),
            "structure": values.get("essay_structure", ""),
            "stage": values.get("essay_stage", ""),
        },
        "timeline": values.get("timeline", {}),
        "message_count": len(values.get("messages", [])),
        "awaiting_resume": bool(values.get("awaiting_resume")),
        "human_requested": bool(values.get("human_requested")),
        "sensitive_categories": sorted({
            d.get("category") for d in values.get("sensitive_disclosures", []) if d.get("category")
        }),
        "escalation_count": len(values.get("escalations", [])),
    }


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Empty message")

    config = _config(req.session_id)
    snapshot = GRAPH.get_state(config)
    existing = snapshot.values if snapshot else {}

    payload: Dict[str, Any] = {"user_input": req.message}
    if not existing:
        seed = new_state(req.profile or {}, session_id=req.session_id)
        payload = {**seed, **payload}

    result = GRAPH.invoke(payload, config)
    route = result.get("route", "respond")
    intent = result.get("intent", "")
    agent = AGENTS.get(route, AGENTS["respond"])
    values = GRAPH.get_state(config).values

    escalations = values.get("escalations", [])
    # "escalated" drives the UI banner: a High-risk escalation raised ON THIS TURN
    # that the student should know a human is looking at. Escalations accumulate
    # across the conversation for the audit trail, so we filter to the current
    # turn - an earlier turn's escalation shouldn't keep the banner lit forever.
    # The distress/crisis handoffs are handled gracefully in-conversation, so they
    # don't trip the banner (excluded inside high_escalations_this_turn).
    current_turn = len(values.get("messages", [])) // 2
    escalated = bool(
        guardrails.high_escalations_this_turn(escalations, current_turn, req.message)
    ) and route != "support"

    return ChatResponse(
        reply=result.get("response", ""),
        intent=intent,
        route=route,
        agent=agent,
        state=_state_summary(values),
        guardrail_flags=result.get("guardrail_flags", []),
        escalated=escalated,
        escalations=escalations,
        awaiting_resume=bool(values.get("awaiting_resume")),
        human_requested=bool(values.get("human_requested")),
    )


@app.get("/api/session/{session_id}")
def get_session(session_id: str) -> Dict[str, Any]:
    snapshot = GRAPH.get_state(_config(session_id))
    values = snapshot.values if snapshot else {}
    messages = values.get("messages", []) if values else []
    return {"state": _state_summary(values), "messages": messages}


@app.post("/api/session/{session_id}/reset")
def reset_session(session_id: str) -> Dict[str, str]:
    # A fresh thread_id is the clean reset; the client generates one. This
    # endpoint exists so the UI can also overwrite the current thread's state.
    GRAPH.update_state(_config(session_id), new_state())
    return {"status": "reset"}


@app.get("/api/agents")
def list_agents() -> List[Dict[str, Any]]:
    return [AGENTS[k] for k in ("discovery", "essay", "planning")]


# ---------------------------------------------------------------------------
# Guardrail observability (Checkpoint 6) - a human reviewer / operator view.
# In a real deployment this sits behind auth.
# ---------------------------------------------------------------------------

@app.get("/api/escalations")
def escalations(limit: int = 200) -> Dict[str, Any]:
    import audit_log
    rows = [r for r in audit_log.read_all() if r.get("event") == "escalation"]
    rows.reverse()
    return {"count": len(rows), "escalations": rows[:limit]}


@app.get("/api/metrics")
def metrics() -> Dict[str, Any]:
    import metrics as _m
    return _m.compute()


# ---------------------------------------------------------------------------
# Static content
# ---------------------------------------------------------------------------

def _load_json(path) -> Any:
    with open(path, "r") as f:
        return json.load(f)


@app.get("/api/resources")
def resources() -> Any:
    return _load_json(PROJECT_ROOT / "resources.json")


@app.get("/api/colleges")
def colleges() -> List[Dict[str, Any]]:
    raw = _load_json(COLLEGE_DATA_FILE).get("colleges", [])
    out = []
    for c in raw:
        out.append({
            "id": c["id"],
            "name": c["name"],
            "location": c.get("location"),
            "state": c.get("state"),
            "description": c.get("description"),
            "acceptance_rate": c.get("acceptance_rate"),
            "avg_gpa": c.get("gpa", {}).get("average"),
            "avg_sat": c.get("sat_scores", {}).get("average"),
            "total_cost": c.get("cost", {}).get("total_cost_of_attendance"),
            "meets_full_need": c.get("cost", {}).get("meets_full_need", False),
            "avg_aid": c.get("cost", {}).get("avg_aid_package"),
            "percent_receiving_aid": c.get("cost", {}).get("percent_receiving_aid"),
            "majors": c.get("academics", {}).get("majors", []),
            "stem_strength": c.get("academics", {}).get("stem_strength", False),
            "first_gen_percent": c.get("student_profile", {}).get("first_gen_percent"),
            "pell_grant_percent": c.get("student_profile", {}).get("pell_grant_percent"),
            "graduation_rate": c.get("student_profile", {}).get("graduation_rate"),
            "undergrad_population": c.get("student_profile", {}).get("undergraduate_population"),
            "essays_required": c.get("admissions", {}).get("essays_required"),
            "application_deadline": college_repo.deadline_of(c["id"]),
            "financial_aid_deadline": c.get("admissions", {}).get("financial_aid_deadline"),
        })
    return out


@app.get("/api/colleges/{college_id}")
def college_detail(college_id: str) -> Dict[str, Any]:
    c = college_repo.get(college_id)
    if not c:
        raise HTTPException(status_code=404, detail="College not found")
    return {**c, "application_deadline": college_repo.deadline_of(college_id)}


@app.get("/api/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Serve the built React app (single-service deploy).
# Set WEB_DIST to override; defaults to web/dist next to this file.
# ---------------------------------------------------------------------------

_DIST = Path(os.getenv("WEB_DIST", PROJECT_ROOT / "web" / "dist"))

if _DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = _DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_DIST / "index.html")
