"""Resilient model calls: plain completion + JSON extraction, with retries.

OpenRouter upstreams occasionally die mid-stream, and native response_format
is unreliable for schema adherence on open models. So: every structured call
is a plain completion with the schema spelled out, JSON extracted from the
text, validated against the Pydantic model, retried on transients and on
schema misses. This is boring on purpose — it never fails silent.
"""
from __future__ import annotations

import json
import re
import time

import litellm

MAX_ATTEMPTS = 4
BASE_DELAY = 3.0

_TRANSIENT = ("provider_unavailable", "midstream", "mid stream", "upstream",
              "rate limit", "429", "502", "503", "504", "timeout", "connection",
              "content=None", "parse")


def call_with_retry(fn, *args, **kwargs):
    """fn(*args, **kwargs) -> result. Retries transient provider errors."""
    last: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            last = exc
            if (not _transient(exc)) or attempt == MAX_ATTEMPTS - 1:
                raise
            time.sleep(BASE_DELAY * (2 ** attempt))
    raise last  # pragma: no cover


def _transient(exc: Exception) -> bool:
    s = str(exc).lower()
    return any(t in s for t in _TRANSIENT)


def chat(model_id: str, api_key: str | None, system: str, user: str,
         max_tokens: int = 1200) -> str:
    """One plain completion with retry. Returns the text content."""
    last: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            r = litellm.completion(
                model=model_id,
                api_key=api_key,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=max_tokens,
                reasoning_effort="low",
                temperature=0.4,
                num_retries=2,
            )
            content = r.choices[0].message.content
            if content:
                return content
            raise ValueError("model returned empty content")
        except Exception as exc:  # noqa: BLE001
            last = exc
            if (not _transient(exc) and not isinstance(exc, ValueError)) or attempt == MAX_ATTEMPTS - 1:
                raise
            time.sleep(BASE_DELAY * (2 ** attempt))
    raise last  # pragma: no cover


def structured(model_id: str, api_key: str | None, system: str, user: str,
               model_cls, max_tokens: int = 1200):
    """Completion whose text must contain the model_cls as JSON. Retries on
    both transient errors and schema misses."""
    schema_json = json.dumps(model_cls.model_json_schema(), indent=0)
    sys_full = (
        f"{system}\n\nOUTPUT CONTRACT: Your entire answer MUST be a single JSON "
        f"object (no prose, no code fences) matching this schema:\n{schema_json}"
    )
    last: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            text = chat(model_id, api_key, sys_full, user, max_tokens)
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if not m:
                raise ValueError(f"no JSON in answer: {text[:120]}")
            return model_cls.model_validate_json(m.group(0))
        except Exception as exc:  # noqa: BLE001
            last = exc
            if attempt == MAX_ATTEMPTS - 1:
                raise
            time.sleep(BASE_DELAY * (2 ** attempt))
    raise last  # pragma: no cover
