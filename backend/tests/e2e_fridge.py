"""E2E: run the fridge-short event through the full engine (no server)."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env.keys.ref")

from app import store
from app.agent import actors, engine
from app.scenarios import SCENARIOS


def main() -> None:
    store.init()
    actors.ensure_roster()
    s = SCENARIOS["fridge-short"]
    eid = store.create_event(s["kind"], s["title"], s["payload"])
    print("event:", eid, flush=True)

    engine.start_event(eid)
    # poll until resolved/failed (max 8 min)
    for _ in range(240):
        time.sleep(2)
        e = store.get_event(eid)
        if e["status"] in {"resolved", "failed", "needs_human"}:
            break
    e = store.get_event(eid)
    print("\n=== STATUS:", e["status"], "===")
    print("outcome:", e.get("outcome"))
    print("\n=== TRANSCRIPT ===")
    for t in store.list_turns(eid):
        fields = f"  {t['fields']}" if t["fields"] else ""
        print(f"[{t['side']} | {t['intent']}] {t['message']}{fields}")
    print("\n=== LEDGER ===", store.ledger_totals())
    if e["status"] == "needs_human":
        d = store.pending_decision_for(eid)
        print("\n=== DECISION CARD ===")
        print(json.dumps(d, indent=1)[:600])


if __name__ == "__main__":
    main()
