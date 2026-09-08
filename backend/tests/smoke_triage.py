"""Quick smoke: triage graph on the fridge-short scenario (no server)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env.keys.ref")

from app import store
from app.agent import actors
from app.agent.gleaner import run_triage_graph
from app.scenarios import SCENARIOS


def main() -> None:
    store.init()
    actors.ensure_roster()
    s = SCENARIOS["fridge-short"]
    eid = store.create_event(s["kind"], s["title"], s["payload"])
    event = store.get_event(eid)
    card, research = run_triage_graph(event)
    print("=== TRIAGE CARD ===")
    print(card.model_dump_json(indent=1))
    print("=== RESEARCH ===")
    print(research[:400])
    store.update_event(eid, triage=card.model_dump(), status="triaged")
    print("event:", eid)


if __name__ == "__main__":
    main()
