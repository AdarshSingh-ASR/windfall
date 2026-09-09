"""E2E: run the unclaimed-property opportunity through the full engine."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import store
from app.agent import clerks, engine
from app.scenarios import SCENARIOS


def main() -> None:
    store.init()
    clerks.ensure_clerks()
    s = SCENARIOS["unclaimed-property"]
    oid = store.create_opportunity(s["kind"], s["source"], s["title"], s["payload"])
    print("opportunity:", oid, flush=True)

    engine.start_opportunity(oid)
    for _ in range(240):
        time.sleep(2)
        o = store.get_opportunity(oid)
        if o["status"] in {"approved", "denied", "failed", "needs_consent", "awaiting"}:
            break
    o = store.get_opportunity(oid)
    print("\n=== STATUS:", o["status"], "===")
    print("outcome:", o.get("outcome"))
    print("\n=== TRANSCRIPT ===")
    for t in store.list_turns(oid):
        fields = f"  {t['fields']}" if t["fields"] else ""
        print(f"[{t['side']} | {t['intent']}] {t['message'][:130]}{fields}")
    print("\n=== LEDGER ===", store.ledger_totals())
    if o["status"] == "needs_consent":
        d = store.pending_decision_for(oid)
        print("\n=== CONSENT CARD ===")
        print(json.dumps(d, indent=1)[:600])


if __name__ == "__main__":
    main()
