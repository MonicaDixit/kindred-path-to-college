"""
Support node - the distress handoff protocol (Checkpoint 6).

The Coordinator routes here when a message shows overwhelm, self-harm language,
or a high-stakes emotional event (missed deadline, scholarship rejection). This
node implements steps 3-4 of the 5-step protocol:

  1. Detect          - Coordinator (hybrid classifier)
  2. Pause           - Coordinator suspends the task agents (awaiting_resume=True)
  3. Acknowledge     - warm, focused acknowledgment; NO positive reframe or task
                       pivot until the student signals readiness
  4. Offer connection- offer a human advisor + support resources (an offer, not
                       a redirect; the student stays in control)
  5. Log & resume    - Coordinator resumes only on an explicit readiness signal

  intent == "crisis"                -> fixed, human-written response + hotlines. No LLM.
  intent == "emotional_support"     -> bounded LLM acknowledgment + human offer + footer.
  intent == "missed_deadline"       -> acknowledge the setback first; alternatives come later.
  intent == "scholarship_rejection" -> acknowledge the loss; minimizing language prohibited.
"""

from __future__ import annotations

from typing import Any, Dict

from kindred_state import KindredState
from llm_client import OpenRouterClient

_llm = OpenRouterClient()

# US-focused. If Kindred ever serves students outside the US, localise this.
_HOTLINES = (
    "  • Call or text **988** — the 988 Suicide & Crisis Lifeline (US), "
    "free and confidential, 24/7\n"
    "  • Text **HOME** to **741741** — the Crisis Text Line\n"
    "  • If you are in immediate danger, call 911 or go to your nearest emergency room"
)

_CRISIS_MESSAGE = (
    "I hear you, and I'm really glad you told me. What you're feeling right now "
    "matters, and you deserve to talk to someone who can be there with you.\n\n"
    "Please reach out to someone right now:\n"
    f"{_HOTLINES}\n\n"
    "You can also talk to a school counselor, a teacher you trust, or someone in "
    "your family. Reaching out is a strong thing to do, not a weak one.\n\n"
    "I'll be here whenever you're ready. Nothing about a college application "
    "matters more than you do."
)

_HUMAN_OFFER = (
    "\n\nWould it help to talk to a real person? If you say \"connect me with an "
    "advisor,\" I'll pass this along so a Kindred advisor can follow up with you. "
    "You're in control of that - it's an offer, not a redirect."
)

_SUPPORT_FOOTER = (
    "\n\n---\n"
    "If it ever feels heavier than this, you don't have to carry it alone: call "
    "or text **988** (988 Suicide & Crisis Lifeline) or text **HOME** to "
    "**741741**, any time."
)

# Step 3: acknowledge WITHOUT reframing positively or pivoting to tasks.
_ACK_SYSTEM = (
    "You are Kindred, a warm, steady presence for a first-generation student who "
    "has just told you they feel overwhelmed, hopeless, or like giving up.\n\n"
    "Respond in 3-4 sentences of warm, plain language. You must ONLY:\n"
    "- acknowledge and name what they seem to be feeling, without minimising it;\n"
    "- let them know it makes sense to feel this way and that they were right to "
    "say something;\n"
    "- tell them there's no pressure and you're not going anywhere.\n\n"
    "You must NOT: give a pep talk, cite statistics, say things will be fine, "
    "reframe the situation as positive, offer college advice, or suggest a next "
    "step. Do not use bullet points, headings, emojis, or the word 'just'. Sound "
    "like a person who cares, not a script."
)

_ACK_FALLBACK = (
    "That sounds really heavy, and it makes complete sense that you're feeling "
    "this way - doing all of this without someone at home who's been through it "
    "is genuinely hard. I'm glad you told me. There's no pressure here at all, "
    "and I'm not going anywhere."
)

_MISSED_DEADLINE_MESSAGE = (
    "I'm sorry - missing a deadline when you've been working hard toward this is "
    "a real setback, and it's okay to feel thrown by it. Before we talk about "
    "what might still be possible, I want to make sure you're okay. How are you "
    "doing with this right now?"
)

_SCHOLARSHIP_REJECTION_MESSAGE = (
    "I'm really sorry. Losing a scholarship you were counting on is a genuine "
    "loss, especially when funding is what makes college feel possible - that's "
    "worth taking a moment with, not rushing past. When you're ready, there are "
    "other funding paths we can look at together, and you haven't lost your "
    "options. For now, how are you holding up?"
)


def support_node(state: KindredState) -> Dict[str, Any]:
    intent = state.get("intent")

    if intent == "crisis":
        return {"response": _CRISIS_MESSAGE + _HUMAN_OFFER}

    if intent == "missed_deadline":
        return {"response": _MISSED_DEADLINE_MESSAGE + _HUMAN_OFFER}

    if intent == "scholarship_rejection":
        return {"response": _SCHOLARSHIP_REJECTION_MESSAGE + _HUMAN_OFFER}

    # emotional_support - bounded acknowledgment, no reframe, no task pivot
    profile = state.get("student_profile", {})
    name = profile.get("name")
    prompt = (
        (f"The student's name is {name}. " if name else "")
        + f"They just said: {state['user_input']!r}\n\n"
        "Acknowledge, following your instructions exactly."
    )
    try:
        body = _llm.call([{"role": "user", "content": prompt}], _ACK_SYSTEM)
    except Exception:  # noqa: BLE001
        body = ""
    if not body or body.startswith("I'm having trouble reaching"):
        body = _ACK_FALLBACK

    return {"response": body.rstrip() + _HUMAN_OFFER + _SUPPORT_FOOTER}
