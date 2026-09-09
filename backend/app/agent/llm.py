"""Model providers for Windfall and the simulated issuing bodies."""
from __future__ import annotations

from functools import lru_cache

from strands.models.litellm import LiteLLMModel

from ..config import ACTOR_MODEL, OPENROUTER_API_KEY, WINDFALL_MODEL

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
def windfall_model() -> LiteLLMModel:
    return _model(WINDFALL_MODEL)


@lru_cache(maxsize=4)
def actor_model() -> LiteLLMModel:
    return _model(ACTOR_MODEL)
