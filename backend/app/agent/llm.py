"""Model providers for Gleaner and the simulated actors.

Two models, two rate-limit buckets: Gleaner (the coordinator) reasons on
gpt-oss-120b; donors, volunteers, and pantry clerks run on gpt-oss-20b.
Both via LiteLLM, so any vendor works by changing one env var.
"""
from __future__ import annotations

import os
from functools import lru_cache

from strands.models.litellm import LiteLLMModel

from ..config import ACTOR_MODEL, GLEANER_MODEL, OPENROUTER_API_KEY

_PARAMS = {
    "temperature": 0.4,
    "max_tokens": 2500,
    "num_retries": 8,
    "reasoning_effort": "low",
}


def _model(model_id: str) -> LiteLLMModel:
    return LiteLLMModel(
        client_args={"api_key": OPENROUTER_API_KEY} if OPENROUTER_API_KEY else {},
        model_id=model_id,
        params=_PARAMS,
    )


@lru_cache(maxsize=4)
def gleaner_model() -> LiteLLMModel:
    return _model(GLEANER_MODEL)


@lru_cache(maxsize=4)
def actor_model() -> LiteLLMModel:
    return _model(ACTOR_MODEL)
