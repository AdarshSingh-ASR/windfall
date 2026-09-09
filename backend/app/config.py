"""Windfall configuration — env-driven."""
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

WINDFALL_MODEL = os.getenv("WINDFALL_MODEL", os.getenv("GLEANER_MODEL", "openrouter/openai/gpt-oss-120b"))
ACTOR_MODEL = os.getenv("WINDFALL_ACTOR_MODEL", os.getenv("GLEANER_ACTOR_MODEL", "openrouter/openai/gpt-oss-20b"))

# pace between program-agent turns (rate-limit friendly)
PACE_S = float(os.getenv("WINDFALL_PACE_S", "6"))

HOUSEHOLD = {
    "name": "A. Rivera",
    "zip": "92507",
    "state": "CA",
    "household_size": 3,
    "income_band": "under 60% state median",
    "utility_provider": "Riverside Power & Light",
    "utility_account": "RPL-4471-992",
    "documents_on_file": [
        "2025 tax return (adjusted gross income confirms under-60% SMI)",
        "LIHEAP approval for 2025-26 season, reference LIHEAP-CA-2026-088412",
        "RPL account statement (last 12 months)",
        "Flight 2214 booking code KX7TQZ (RIV→DEN, 2026-08-14, arrived 3h41m late)",
        "State ID matching former address 9 Corbin St, Riverside CA (2019-2021)",
    ],
}
