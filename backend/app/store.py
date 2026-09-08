"""SQLite store: events, conversations, decisions, ledger, activity."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "gleaner.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,              -- donation_offer | surge_need | volunteer_cancel | logistics
  title TEXT NOT NULL,
  payload TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'new',   -- new | triaged | working | needs_human | resolved | failed
  triage TEXT,
  outcome TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS turns (
  id TEXT PRIMARY KEY,
  event_id TEXT NOT NULL,
  side TEXT NOT NULL,              -- gleaner | actor:<id> | system
  intent TEXT NOT NULL,
  message TEXT NOT NULL,
  fields TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS decisions (
  id TEXT PRIMARY KEY,
  event_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  question TEXT NOT NULL,
  options TEXT NOT NULL DEFAULT '[]',
  context TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'pending',
  answer_note TEXT DEFAULT '',
  created_at TEXT NOT NULL,
  answered_at TEXT
);
CREATE TABLE IF NOT EXISTS ledger (
  id TEXT PRIMARY KEY,
  event_id TEXT,
  metric TEXT NOT NULL,            -- meals | volunteer_hours | kg_saved | usd_value
  amount REAL NOT NULL,
  note TEXT DEFAULT '',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS actors (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,              -- donor | volunteer | pantry | partner
  name TEXT NOT NULL,
  persona TEXT NOT NULL,
  state TEXT NOT NULL DEFAULT '{}'
);
"""


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    return c


def init() -> None:
    with _conn() as c:
        c.executescript(SCHEMA)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


# ------------------------------------------------------------------ events --

def create_event(kind: str, title: str, payload: dict) -> str:
    eid = new_id("evt")
    with _conn() as c:
        c.execute(
            "INSERT INTO events (id, kind, title, payload, status, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (eid, kind, title, json.dumps(payload), "new", _now(), _now()),
        )
    return eid


def update_event(eid: str, **kw) -> None:
    cols, vals = [], []
    for k, v in kw.items():
        cols.append(f"{k}=?")
        vals.append(json.dumps(v) if isinstance(v, (dict, list)) else v)
    cols.append("updated_at=?")
    vals.append(_now())
    vals.append(eid)
    with _conn() as c:
        c.execute(f"UPDATE events SET {', '.join(cols)} WHERE id=?", vals)


def get_event(eid: str) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM events WHERE id=?", (eid,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["payload"] = json.loads(d["payload"] or "{}")
    d["triage"] = json.loads(d["triage"]) if d["triage"] else None
    return d


def list_events(limit: int = 100) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM events ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    out = []
    for row in rows:
        d = dict(row)
        d["payload"] = json.loads(d["payload"] or "{}")
        d["triage"] = json.loads(d["triage"]) if d["triage"] else None
        out.append(d)
    return out


# ------------------------------------------------------------------- turns --

def add_turn(event_id: str, side: str, intent: str, message: str, fields: dict | None = None) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO turns (id, event_id, side, intent, message, fields, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (new_id("trn"), event_id, side, intent, message, json.dumps(fields or {}), _now()),
        )


def list_turns(event_id: str) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM turns WHERE event_id=? ORDER BY created_at, id", (event_id,)
        ).fetchall()
    out = []
    for row in rows:
        d = dict(row)
        d["fields"] = json.loads(d["fields"] or "{}")
        out.append(d)
    return out


# --------------------------------------------------------------- decisions --

def create_decision(event_id: str, kind: str, question: str, options: list[str], context: dict) -> str:
    did = new_id("dec")
    with _conn() as c:
        c.execute(
            "INSERT INTO decisions (id, event_id, kind, question, options, context, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (did, event_id, kind, question, json.dumps(options), json.dumps(context), _now()),
        )
    return did


def get_decision(did: str) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM decisions WHERE id=?", (did,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["options"] = json.loads(d["options"] or "[]")
    d["context"] = json.loads(d["context"] or "{}")
    return d


def answer_decision(did: str, status: str, note: str = "") -> None:
    with _conn() as c:
        c.execute(
            "UPDATE decisions SET status=?, answer_note=?, answered_at=? WHERE id=?",
            (status, note, _now(), did),
        )


def pending_decision_for(event_id: str) -> dict | None:
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM decisions WHERE event_id=? AND status='pending' ORDER BY created_at DESC",
            (event_id,),
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    d["options"] = json.loads(d["options"] or "[]")
    d["context"] = json.loads(d["context"] or "{}")
    return d


def list_decisions(limit: int = 50) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM decisions ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    out = []
    for row in rows:
        d = dict(row)
        d["options"] = json.loads(d["options"] or "[]")
        d["context"] = json.loads(d["context"] or "{}")
        out.append(d)
    return out


# ------------------------------------------------------------------ ledger --

def ledger_add(event_id: str, metric: str, amount: float, note: str = "") -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO ledger (id, event_id, metric, amount, note, created_at) VALUES (?,?,?,?,?,?)",
            (new_id("led"), event_id, metric, amount, note, _now()),
        )


def ledger_totals() -> dict:
    with _conn() as c:
        rows = c.execute("SELECT metric, SUM(amount) s FROM ledger GROUP BY metric").fetchall()
    return {r["metric"]: r["s"] for r in rows}


# ------------------------------------------------------------------ actors --

def seed_actor(aid: str, kind: str, name: str, persona: str, state: dict | None = None) -> None:
    with _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO actors (id, kind, name, persona, state) VALUES (?,?,?,?,?)",
            (aid, kind, name, persona, json.dumps(state or {})),
        )


def get_actor(aid: str) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM actors WHERE id=?", (aid,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["state"] = json.loads(d["state"] or "{}")
    return d


def list_actors() -> list[dict]:
    with _conn() as c:
        rows = c.execute("SELECT * FROM actors").fetchall()
    out = []
    for row in rows:
        d = dict(row)
        d["state"] = json.loads(d["state"] or "{}")
        out.append(d)
    return out
