"""Gemini client.

Every agent decision that needs judgement or drafting routes through here, so
the deployed application always makes its LLM calls via the Gemini API.

If no API key is configured the client falls back to deterministic templates so
the agent loops remain runnable offline (tests, local demos). Fallback output is
flagged so it can never be mistaken for a model decision in the audit log.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any

from .config import settings


@dataclass
class LLMResult:
    data: dict[str, Any]
    model: str
    latency_ms: int
    used_fallback: bool = False


_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(text: str) -> dict[str, Any]:
    """Models sometimes wrap JSON in prose or fences; take the outermost object."""
    match = _JSON_BLOCK.search(text or "")
    if not match:
        raise ValueError("no JSON object in model response")
    return json.loads(match.group(0))


class GeminiClient:
    def __init__(self) -> None:
        self._client = None
        if settings.gemini_api_key:
            from google import genai

            self._client = genai.Client(api_key=settings.gemini_api_key)

    @property
    def available(self) -> bool:
        return self._client is not None

    def decide(
        self,
        *,
        system: str,
        prompt: str,
        schema_hint: str,
        fallback: dict[str, Any],
        temperature: float = 0.3,
    ) -> LLMResult:
        """Ask Gemini for a structured decision.

        Returns the fallback (clearly marked) if the API is unavailable or the
        response cannot be parsed - an agent tick must never crash the whole run
        because one call failed.
        """
        if not self._client:
            return LLMResult(fallback, "fallback:none", 0, used_fallback=True)

        contents = f"{prompt}\n\nRespond with a single JSON object matching: {schema_hint}"
        started = time.monotonic()
        try:
            from google.genai import types

            response = self._client.models.generate_content(
                model=settings.gemini_model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    temperature=temperature,
                    response_mime_type="application/json",
                ),
            )
            latency = int((time.monotonic() - started) * 1000)
            return LLMResult(_extract_json(response.text), settings.gemini_model, latency)
        except Exception as exc:  # noqa: BLE001 - degrade, never break the tick
            latency = int((time.monotonic() - started) * 1000)
            marked = dict(fallback)
            marked["_error"] = f"{type(exc).__name__}: {exc}"
            return LLMResult(marked, f"fallback:{settings.gemini_model}", latency, True)


_client: GeminiClient | None = None


def get_client() -> GeminiClient:
    global _client
    if _client is None:
        _client = GeminiClient()
    return _client
