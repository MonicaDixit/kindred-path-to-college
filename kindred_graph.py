"""
LangGraph wiring for the Kindred multi-agent system.

    user_input
        │
        ▼
   ┌───────────┐   kindred_coordinator.py — deterministic + PRE-GENERATION guardrails
   │Coordinator│   • hybrid safety classifier (distress / crisis / scope / disclosure)
   │           │   • distress handoff pause, profile-contradiction check, escalation
   │           │   • classify task intent, pick route
   └────┬──────┘
        │ conditional edge on state["route"]
        ├── "support"   ──► support_node.py    safety: crisis / distress / high-stakes
        ├── "discovery" ──► discovery_node.py  LLM + RAG (case studies, ranker)
        ├── "essay"     ──► essay_node.py      LLM + RAG (essay_examples.json)
        ├── "planning"  ──► planning_node.py   deterministic, NO LLM
        └── "respond"   ──► help_node          menu / scope redirect / re-entry
                                │
                                ▼
                        ┌───────────────┐   validate_node.py — POST-GENERATION guardrails
                        │   Validate    │   schema / calibration / authorship checks,
                        │               │   hedge or regenerate, append the assistant turn
                        └──────┬────────┘
                               ▼
                              END   → caller reads state["response"]

Agents set `response` (+ domain state); the Validate node appends the final
assistant message to `messages`. Compiled with a MemorySaver checkpointer keyed
by `thread_id`.
"""

from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from discovery_node import discovery_node
from essay_node import essay_node
from kindred_coordinator import coordinator_node, help_node
from kindred_state import KindredState
from planning_node import planning_node
from support_node import support_node
from validate_node import validate_node


def build_graph():
    g = StateGraph(KindredState)

    g.add_node("coordinator", coordinator_node)
    g.add_node("support", support_node)
    g.add_node("discovery", discovery_node)
    g.add_node("essay", essay_node)
    g.add_node("planning", planning_node)
    g.add_node("respond", help_node)
    g.add_node("validate", validate_node)

    g.add_edge(START, "coordinator")
    g.add_conditional_edges(
        "coordinator",
        lambda s: s.get("route", "respond"),
        {
            "support": "support",
            "discovery": "discovery",
            "essay": "essay",
            "planning": "planning",
            "respond": "respond",
        },
    )
    for node in ("support", "discovery", "essay", "planning", "respond"):
        g.add_edge(node, "validate")
    g.add_edge("validate", END)

    return g.compile(checkpointer=MemorySaver())


# module-level singleton for the CLI / API
GRAPH = build_graph()
