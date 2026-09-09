"""E2E: settlement flow WITH the consent gate answered via the store."""
from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import store
from app.agent import clerks, engine
from app.scenarios import SCENARIOS


def auto_consent(oid: str) -> None:
    """Simulate the claimant approving the consent card a few seconds in."""
    for _ in range(60):
        time.sleep(2)
        d = store.pending_decision_for(oid)
        if d:
            store.answer_decision(d["id"], "approved", "yes, file it")
            print(">>> claimant approved consent", flush=True)
            return


def main() -> None:
    store.init()
    clerks.ensure_clerks()
    s = SCENARIOS["class-settlement"]
    oid = store.create_opportunity(s["kind"], s["source"], s["title"], s["payload"])
    print("opportunity:", oid, flush=True)

    threading.Thread(target=auto_consent, args=(oid,), daemon=True).start()
    engine.start_opportunity(oid)

    for _ in range(240):
        time.sleep(2)
        o = store.get_opportunity(oid)
        if o["status"] in {"approved", "denied", "failed", "resolved", "awaiting"}:
            break
    o = store.get_opportunity(oid)
    print("\n=== STATUS:", o["status"], "===")
    print("outcome:", o.get("outcome"))
    print("\n=== TRANSCRIPT ===")
    for t in store.list_turns(oid):
        print(f"[{t['side']} | {t['intent']}] {t['message'][:120]}")
    print("\n=== LEDGER ===", store.ledger_totals())


if __name__ == "__main__":
    main()
