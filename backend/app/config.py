"""Gleaner configuration — env-driven."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

logging.getLogger("LiteLLM").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.WARNING)

SESSIONS_DIR = BACKEND_DIR / "sessions"
SESSIONS_DIR.mkdir(exist_ok=True)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

GLEANER_MODEL = os.getenv("GLEANER_MODEL", "openrouter/openai/gpt-oss-120b")
ACTOR_MODEL = os.getenv("GLEANER_ACTOR_MODEL", "openrouter/openai/gpt-oss-20b")

# pace between actor turns (rate-limit friendly)
PACE_S = float(os.getenv("GLEANER_PACE_S", "6"))

CITY = "Riverside"
