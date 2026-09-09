"""SQLite store: opportunities, claims, decisions, ledger, activity."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "windfall.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS opportunities (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  source TEXT NOT NULL,
  title TEXT NOT NULL,
  payload TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'new',  -- new | triaged | filing | needs_consent | awaiting | approved | denied | appeal | failed
  triage TEXT,
  est_low REAL DEFAULT 0,
  est_high REAL DEFAULT 0,
  outcome TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS turns (
  id TEXT PRIMARY KEY,
  opportunity_id TEXT NOT NULL,
  side TEXT NOT NULL,              -- windfall | clerk:<id> | system
  intent TEXT NOT NULL,
  message TEXT NOT NULL,
  fields TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS decisions (
  id TEXT PRIMARY KEY,
  opportunity_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  question TEXT NOT NULL,
  context TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'pending',
  answer_note TEXT DEFAULT '',
  created_at TEXT NOT NULL,
  answered_at TEXT
);
CREATE TABLE IF NOT EXISTS ledger (
  id TEXT PRIMARY KEY,
  opportunity_id TEXT,
  label TEXT NOT NULL,
  amount REAL NOT NULL,
  kind TEXT NOT NULL DEFAULT 'recovered',  -- recovered | annualized | pending
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS clerks (
  id TEXT PRIMARY KEY,
  org TEXT NOT NULL,
  role TEXT NOT NULL,
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


def create_opportunity(kind: str, source: str, title: str, payload: dict) -> str:
    oid = new_id("opp")
    with _conn() as c:
        c.execute(
            "INSERT INTO opportunities (id, kind, source, title, payload, status, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (oid, kind, source, title, json.dumps(payload), "new", _now(), _now()),
        )
    return oid


def update_opportunity(oid: str, **kw) -> None:
    cols, vals = [], []
    for k, v in kw.items():
        cols.append(f"{k}=?")
        vals.append(json.dumps(v) if isinstance(v, (dict, list)) else v)
    cols.append("updated_at=?")
    vals.append(_now())
    vals.append(oid)
    with _conn() as c:
        c.execute(f"UPDATE opportunities SET {', '.join(cols)} WHERE id=?", vals)


def get_opportunity(oid: str) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM opportunities WHERE id=?", (oid,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["payload"] = json.loads(d["payload"] or "{}")
    d["triage"] = json.loads(d["triage"]) if d["triage"] else None
    return d


def list_opportunities(limit: int = 100) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM opportunities ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    out = []
    for row in rows:
        d = dict(row)
        d["payload"] = json.loads(d["payload"] or "{}")
        d["triage"] = json.loads(d["triage"]) if d["triage"] else None
        out.append(d)
    return out


def add_turn(oid: str, side: str, intent: str, message: str, fields: dict | None = None) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO turns (id, opportunity_id, side, intent, message, fields, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (new_id("trn"), oid, side, intent, message, json.dumps(fields or {}), _now()),
        )


def list_turns(oid: str) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM turns WHERE opportunity_id=? ORDER BY created_at, id", (oid,)
        ).fetchall()
    out = []
    for row in rows:
        d = dict(row)
        d["fields"] = json.loads(d["fields"] or "{}")
        out.append(d)
    return out


def create_decision(oid: str, kind: str, question: str, context: dict) -> str:
    did = new_id("dec")
    with _conn() as c:
        c.execute(
            "INSERT INTO decisions (id, opportunity_id, kind, question, context, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (did, oid, kind, question, json.dumps(context), _now()),
        )
    return did


def get_decision(did: str) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM decisions WHERE id=?", (did,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["context"] = json.loads(d["context"] or "{}")
    return d


def answer_decision(did: str, status: str, note: str = "") -> None:
    with _conn() as c:
        c.execute(
            "UPDATE decisions SET status=?, answer_note=?, answered_at=? WHERE id=?",
            (status, note, _now(), did),
        )


def pending_decision_for(oid: str) -> dict | None:
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM decisions WHERE opportunity_id=? AND status='pending' ORDER BY created_at DESC",
            (oid,),
        ).fetchone()
    if not row:
        return None
    d = dict(row)
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
        d["context"] = json.loads(d["context"] or "{}")
        out.append(d)
    return out


def ledger_add(oid: str, label: str, amount: float, kind: str = "recovered") -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO ledger (id, opportunity_id, label, amount, kind, created_at) VALUES (?,?,?,?,?,?)",
            (new_id("led"), oid, label, amount, kind, _now()),
        )


def ledger_totals() -> dict:
    with _conn() as c:
        rows = c.execute("SELECT kind, SUM(amount) s FROM ledger GROUP BY kind").fetchall()
    return {r["kind"]: r["s"] for r in rows}


def seed_clerk(cid: str, org: str, role: str, persona: str, state: dict | None = None) -> None:
    with _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO clerks (id, org, role, persona, state) VALUES (?,?,?,?,?)",
            (cid, org, role, persona, json.dumps(state or {})),
        )


def get_clerk(cid: str) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM clerks WHERE id=?", (cid,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["state"] = json.loads(d["state"] or "{}")
    return d


def list_clerks() -> list[dict]:
    with _conn() as c:
        rows = c.execute("SELECT * FROM clerks").fetchall()
    out = []
    for row in rows:
        d = dict(row)
        d["state"] = json.loads(d["state"] or "{}")
        out.append(d)
    return out
