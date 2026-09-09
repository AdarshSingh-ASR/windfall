"""Windfall API: opportunities in, live streams out, consents answered."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import store
from .agent import clerks, engine
from .config import HOUSEHOLD
from .scenarios import SCENARIOS

app = FastAPI(title="Windfall", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class DecisionAnswer(BaseModel):
    status: str  # approved | declined
    note: str = ""


@app.on_event("startup")
def _startup() -> None:
    store.init()
    clerks.ensure_clerks()


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "service": "windfall"}


@app.get("/api/household")
def household() -> dict:
    return {"household": HOUSEHOLD}


@app.get("/api/scenarios")
def scenarios() -> dict:
    return {"scenarios": [{"id": k, **v} for k, v in SCENARIOS.items()]}


@app.get("/api/clerks")
def clerks_list() -> dict:
    return {"clerks": store.list_clerks()}


@app.get("/api/opportunities")
def opportunities_list() -> dict:
    out = []
    for o in store.list_opportunities():
        o["turn_count"] = len(store.list_turns(o["id"]))
        out.append(o)
    return {"opportunities": out}


@app.get("/api/opportunities/{oid}")
def opportunity_detail(oid: str) -> dict:
    o = store.get_opportunity(oid)
    if not o:
        return {"error": "not found"}
    o["turns"] = store.list_turns(oid)
    o["decisions"] = [d for d in store.list_decisions() if d["opportunity_id"] == oid]
    return o


@app.post("/api/opportunities/seed/{seed_id}")
def seed_opportunity(seed_id: str) -> dict:
    if seed_id not in SCENARIOS:
        return {"error": "unknown scenario"}
    s = SCENARIOS[seed_id]
    oid = store.create_opportunity(s["kind"], s["source"], s["title"], s["payload"])
    engine.start_opportunity(oid)
    return {"id": oid}


@app.get("/api/decisions")
def decisions_list() -> dict:
    return {"decisions": store.list_decisions()}


@app.post("/api/decisions/{did}/answer")
def answer_decision(did: str, body: DecisionAnswer) -> dict:
    d = store.get_decision(did)
    if not d:
        return {"error": "not found"}
    if d["status"] != "pending":
        return {"error": f"already {d['status']}"}
    status = "approved" if body.status.lower().startswith("a") else "declined"
    store.answer_decision(did, status, body.note)
    return {"ok": True, "status": status}


@app.get("/api/ledger")
def ledger() -> dict:
    return {"totals": store.ledger_totals()}
