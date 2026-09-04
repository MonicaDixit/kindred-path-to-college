"""
OpenRouter LLM Client
FIXED VERSION - Corrected imports
"""

import time
import requests
import json
from typing import Optional, Dict, Any
from config import (
    OPENROUTER_API_KEY, LLM_MODEL, MAX_TOKENS, TEMPERATURE,
    LLM_FALLBACK_MODEL, LLM_TIMEOUT, LLM_MAX_RETRIES, LLM_DISABLE_REASONING,
)

# Errors that are worth retrying (transient): timeouts, connection drops,
# rate limits, and upstream 5xx from the model provider.
_RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}


class OpenRouterClient:
    """Client for OpenRouter LLM API, with retries + a fallback model."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or OPENROUTER_API_KEY
        self.model = model or LLM_MODEL
        self.base_url = "https://openrouter.ai/api/v1"

    def call(self, messages: list, system_prompt: Optional[str] = None) -> str:
        """
        Call the LLM and return its text.

        Retries transient failures with exponential backoff, then tries the
        configured fallback model before giving up.
        """
        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}] + messages

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://kindred-path2college.local",
            "X-Title": "Kindred Path2College",
        }

        models = [self.model]
        if LLM_FALLBACK_MODEL and LLM_FALLBACK_MODEL != self.model:
            models.append(LLM_FALLBACK_MODEL)

        last_error = "unknown error"
        for model in models:
            payload = {
                "model": model,
                "messages": messages,
                "max_tokens": MAX_TOKENS,
                "temperature": TEMPERATURE,
            }
            if LLM_DISABLE_REASONING:
                # OpenRouter: suppress hidden chain-of-thought on reasoning models.
                payload["reasoning"] = {"enabled": False}
            for attempt in range(1, LLM_MAX_RETRIES + 1):
                try:
                    response = requests.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                        # (connect timeout, read timeout)
                        timeout=(10, LLM_TIMEOUT),
                    )
                    if response.status_code == 200:
                        result = response.json()
                        return result["choices"][0]["message"]["content"]

                    last_error = f"{response.status_code} - {response.text[:200]}"
                    if response.status_code not in _RETRYABLE_STATUS:
                        break  # non-transient (e.g. 401/404) - try next model
                except (requests.Timeout, requests.ConnectionError) as e:
                    last_error = f"{type(e).__name__}: {e}"
                except Exception as e:  # noqa: BLE001
                    last_error = str(e)
                    break

                if attempt < LLM_MAX_RETRIES:
                    time.sleep(min(2 ** attempt, 8))  # 2s, 4s, 8s

        return (
            "I'm having trouble reaching the language model right now "
            f"(the free tier may be busy). Please try again in a moment. [{last_error}]"
        )

    def parse_action(self, text: str) -> tuple:
        """
        Parse LLM output for THOUGHT, ACTION, INPUT
        
        Expected format:
        THOUGHT: ...reasoning...
        ACTION: tool_name
        INPUT: {"param": "value"}
        """
        
        lines = text.split('\n')
        thought = ""
        action = None
        input_str = None
        
        for line in lines:
            if line.startswith('THOUGHT:'):
                thought = line.replace('THOUGHT:', '').strip()
            elif line.startswith('ACTION:'):
                action = line.replace('ACTION:', '').strip()
            elif line.startswith('INPUT:'):
                input_str = line.replace('INPUT:', '').strip()
        
        return thought, action, input_str