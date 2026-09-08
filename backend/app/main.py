"""Gleaner API: events in, live streams out, decisions answered."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import store
from .agent import actors, engine
from .scenarios import SCENARIOS

app = FastAPI(title="Gleaner", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class NewEvent(BaseModel):
    kind: str = "donation_offer"
    title: str
    payload: dict = {}


class DecisionAnswer(BaseModel):
    status: str  # approved | declined
    note: str = ""


@app.on_event("startup")
def _startup() -> None:
    store.init()
    actors.ensure_roster()


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "service": "gleaner"}


@app.get("/api/scenarios")
def scenarios() -> dict:
    return {"scenarios": [{"id": k, **v} for k, v in SCENARIOS.items()]}


@app.get("/api/actors")
def actors_list() -> dict:
    return {"actors": store.list_actors()}


@app.get("/api/events")
def events_list() -> dict:
    out = []
    for e in store.list_events():
        e["turn_count"] = len(store.list_turns(e["id"]))
        out.append(e)
    return {"events": out}


@app.get("/api/events/{eid}")
def event_detail(eid: str) -> dict:
    e = store.get_event(eid)
    if not e:
        return {"error": "not found"}
    e["turns"] = store.list_turns(eid)
    e["decisions"] = [d for d in store.list_decisions() if d["event_id"] == eid]
    return e


@app.post("/api/events")
def create_event(body: NewEvent) -> dict:
    eid = store.create_event(body.kind, body.title, body.payload)
    engine.start_event(eid)
    return {"id": eid}


@app.post("/api/events/seed/{seed_id}")
def seed_event(seed_id: str) -> dict:
    if seed_id not in SCENARIOS:
        return {"error": "unknown scenario"}
    s = SCENARIOS[seed_id]
    eid = store.create_event(s["kind"], s["title"], s["payload"])
    engine.start_event(eid)
    return {"id": eid}


@app.get("/api/decisions")
def decisions_list() -> dict:
    return {"decisions": store.list_decisions()}


@app.get("/api/decisions/{did}")
def decision_detail(did: str) -> dict:
    d = store.get_decision(did)
    return d or {"error": "not found"}


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
