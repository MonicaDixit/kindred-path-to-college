"""
Conversational CLI for the Kindred multi-agent system.

    python3 kindred_cli.py                # interactive
    python3 kindred_cli.py --demo         # scripted 4-turn walkthrough (Elena)

Each run is one student conversation (thread_id). State persists between turns
via the graph's checkpointer, so follow-up questions keep full context.
"""

from __future__ import annotations

import sys
import uuid

from kindred_graph import GRAPH
from kindred_state import new_state

BANNER = "=" * 70


def _turn(student_id: str, text: str, first: bool) -> str:
    config = {"configurable": {"thread_id": student_id}}
    payload = {"user_input": text}
    if first:
        payload = {**new_state(session_id=student_id), **payload}
    result = GRAPH.invoke(payload, config)
    intent = result.get("intent", "?")
    flags = result.get("guardrail_flags") or []
    tail = f"  flags={flags}" if flags else ""
    print(f"\n[coordinator] intent={intent} -> route={result.get('route')}{tail}")
    return result.get("response", "(no response)")


def interactive() -> None:
    student_id = f"student_{uuid.uuid4().hex[:8]}"
    print(BANNER)
    print("KINDRED - College Application Guide (multi-agent / LangGraph)")
    print(BANNER)
    print("Type your questions. 'quit' to exit.\n")
    print("Try:  I'm pre-med, 3.2 GPA, 1300 SAT, D1 soccer, first-gen. Give me colleges.\n")

    first = True
    while True:
        try:
            text = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            return
        if not text:
            continue
        if text.lower() in ("quit", "exit"):
            print("Goodbye!")
            return
        answer = _turn(student_id, text, first)
        first = False
        print(f"\nKindred:\n{answer}\n")
        print("-" * 70)


DEMO_TURNS = [
    "I'm Elena. I'm pre-med, 3.2 GPA, 1280 SAT, D1 soccer, first-gen. Give me colleges.",
    "Tell me about Stanford. What's the deadline?",
    "I wrote my Stanford essay. Here's the draft: The morning after our double-overtime "
    "loss I went to the library instead of the training room. I wanted to understand why "
    "my body failed at minute 78. I read about lactate thresholds until closing, then "
    "asked my bio teacher if I could design an independent study around sports physiology. "
    "She said yes. That project became the reason I want to be a doctor - not to fix "
    "bodies abstractly, but to answer the specific question of why this body, this day.",
    "What's my deadline order? Help me plan my weeks.",
]


def demo() -> None:
    student_id = "elena_demo"
    print(BANNER)
    print("DEMO: Elena's conversation (4 turns)")
    print(BANNER)
    for i, text in enumerate(DEMO_TURNS):
        print(f"\n{'#' * 70}\nYou: {text}\n{'#' * 70}")
        answer = _turn(student_id, text, first=(i == 0))
        print(f"\nKindred:\n{answer}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        demo()
    else:
        interactive()
