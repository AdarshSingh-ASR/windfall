"""The Gleaner engine: event in -> triage -> autonomous execution -> outcomes.

For each event:
  1. triage graph -> TriageCard
  2. if needs_human: Decision card for the coordinator; block until answered
  3. else: execute the plan as a conversation with the affected actors
     (each actor is an agent that can accept, counter, or decline)
  4. record outcomes in the impact ledger

Quiet by design: the human sees one Decision Card only when judgment is needed.
"""
from __future__ import annotations

import threading
import time
import traceback

from .. import store
from ..config import GLEANER_MODEL, OPENROUTER_API_KEY, PACE_S
from ..protocol import Msg, TriageCard
from .actors import actor_reply
from .gleaner import run_triage_graph
from .resilience import call_with_retry, structured

_running: set[str] = set()
_lock = threading.Lock()
_sem = threading.BoundedSemaphore(2)  # two events at once, gentle on rate limits

GLEANER_EXEC_PROMPT = """You are Gleaner, the coordination agent for the Riverside Food Network.

THE PLAN: {plan}

RESEARCH: {research}

ROSTER (id — name, state):
{roster}

You now conduct the conversations that execute this plan. Rules:
- One Msg per step: message the ONE actor who unblocks the most (max {max_steps} steps total).
- intent: ask | offer | confirm | decline | reroute | thank | update
- Be warm, concrete, brief. Put quantities and times in fields when they matter.
- When every needed actor has accepted and logistics are set, reply with intent=done
  (`to` = the main actor, message = one-line summary of what was arranged).
- If an actor declines and no roster switch can absorb it, send intent=escalate with
  `to`='coordinator' and message = the ONE question for the human coordinator.
- Priya drives weekday evenings after 18:00 and weekends (hatchback, 120 kg).
- Marco drives mornings only (pickup truck, 400 kg, max 25 min one-way).
- Jun drives weekday afternoons 12:00-19:00 (cargo van, 350 kg, insulated, no fridge).
- For 3-6pm windows, Jun is the right driver; mornings: Marco; evenings: Priya.
- Match each pantry's cold capacity before assigning volume; reroute overflow
  to the actor who can absorb it (St. Mary's takes same-day volume).
- Mixed produce travels fine in insulated crates in any cargo vehicle; do not
  demand refrigerated vans for it. Dairy/meat/frozen DO need cold chain.
- A regular volunteer van that fits the kg IS a valid plan for produce.
- Dairy needs cold chain, but the CARGO is what needs to stay cold — insulated
  blankets/crates in any van work for short runs; do not demand refrigerated
  vehicles the roster doesn't have. Food-bank loads: St. Mary's has 2 drivers.
- An actor's ACCEPT of the specific ask closes that thread — do not re-confirm
  what was already accepted; move to the next unblocked step.
- Escalate ONLY when the plan is genuinely blocked (spend, conflict, or no actor
  can absorb) — a timing mismatch that another volunteer solves is NOT blocked.
- Do not end without intent=done or intent=escalate.
"""


def start_event(eid: str) -> None:
    with _lock:
        if eid in _running:
            return
        _running.add(eid)
    threading.Thread(target=_run, args=(eid,), daemon=True).start()


def _run(eid: str) -> None:
    try:
        with _sem:
            _run_locked(eid)
    except Exception as exc:  # noqa: BLE001
        store.update_event(eid, status="failed", outcome=f"Engine failure: {exc}")
        store.add_turn(eid, "system", "error", f"Engine failure: {exc}")
        traceback.print_exc()
    finally:
        with _lock:
            _running.discard(eid)


def _run_locked(eid: str) -> None:
    event = store.get_event(eid)
    if not event:
        return

    store.update_event(eid, status="working")
    store.add_turn(eid, "system", "phase", "Triaging: intake -> research -> plan")

    card, research_text = call_with_retry(run_triage_graph, event)
    store.update_event(eid, triage=card.model_dump(), status="triaged")
    store.add_turn(eid, "system", "triage",
                   f"{card.headline} — {card.action_plan}",
                   {"urgency": card.urgency, "category": card.category})

    if card.needs_human and card.human_question:
        did = store.create_decision(
            eid, _decision_kind(card), card.human_question,
            ["Approve", "Decline"],
            {"card": card.model_dump(), "research": research_text[:800]},
        )
        store.update_event(eid, status="needs_human")
        answer = _wait_answer(eid, did)
        if answer is None:
            store.update_event(eid, status="failed", outcome="decision timed out")
            return
        dec = store.get_decision(did)
        store.add_turn(eid, "system", "coordinator",
                       f"Coordinator: {answer}{(' — ' + dec['answer_note']) if dec and dec['answer_note'] else ''}")
        if answer == "declined":
            store.update_event(eid, status="resolved", outcome="Coordinator declined the proposed action")
            return

    # ---- autonomous execution: talk to the actors ----
    _execute(event, card, research_text)


def _execute(event: dict, card: TriageCard, research_text: str) -> None:
    eid = event["id"]
    max_steps = 8
    system = GLEANER_EXEC_PROMPT.format(
        plan=card.action_plan,
        research=research_text[:600],
        roster=_roster_text(),
        max_steps=max_steps,
    )

    steps = 0
    last_reply_text = "(no replies yet — you are opening the conversations)"
    last_actor_id = ""
    last_reply_accept = False
    declined: dict[str, int] = {}  # actor id -> decline count
    done_threads: set[str] = set()  # actors whose ask was explicitly accepted

    while steps < max_steps:
        time.sleep(PACE_S)
        steps += 1
        prompt = (
            f"EVENT: {event['title']} — details: {event['payload']}\n"
            f"CONVERSATIONS SO FAR:\n{_turns_text(eid)}\n"
            f"LAST ACTOR REPLY ({last_actor_id or 'n/a'}): {last_reply_text}\n\n"
            f"Step {steps} of {max_steps}. Your next Msg."
            + ("\nIMPORTANT: You already asked " + ", ".join(f"{a} ({n}x)" for a, n in declined.items())
               + " and it did not work. Do NOT repeat the same ask to the same actor; reroute to a "
                 "different actor or change the plan materially." if declined else "")
        )
        msg = _safe_msg(system, prompt)
        if msg is None:
            break

        if msg.intent == "done":
            store.add_turn(eid, "system", "done", msg.message)
            _record_impact(eid, event, msg)
            store.update_event(eid, status="resolved", outcome=msg.message)
            return

        if msg.intent == "escalate" or msg.to == "coordinator":
            _escalate(eid, msg.message)
            return

        if msg.to in done_threads:
            continue  # thread already closed by an explicit accept; don't re-ask
        if (
            msg.intent in {"confirm", "ask"}
            and msg.to == last_actor_id
            and last_reply_accept
        ):
            # the actor just accepted this thread; treat it as closed and move on
            done_threads.add(msg.to)
            continue

        actor = store.get_actor(msg.to)
        if not actor:
            store.add_turn(
                eid, "system", "error",
                f"'{msg.to}' is not on the roster. Valid ids: "
                + ", ".join(a["id"] for a in store.list_actors())
                + ". Reroute to one of these.",
            )
            continue
        store.add_turn(eid, "gleaner", msg.intent, msg.message, msg.fields)
        time.sleep(PACE_S)
        reply = actor_reply(actor, msg.message, event["title"] + ": " + card.headline)
        store.add_turn(eid, f"actor:{actor['id']}",
                       "accept" if reply.accept else "decline",
                       reply.message, reply.fields)
        last_reply_text = f"accept={reply.accept} — {reply.message} fields={reply.fields}"
        last_actor_id = actor["id"]
        last_reply_accept = reply.accept
        if reply.accept:
            declined.pop(actor["id"], None)
        else:
            declined[actor["id"]] = declined.get(actor["id"], 0) + 1

    # ran out of steps without done/escalate
    _escalate(eid, "Gleaner couldn't close this within its step budget. " +
              _last_open_question(eid))


def _safe_msg(system: str, prompt: str) -> Msg | None:
    try:
        return structured(GLEANER_MODEL, OPENROUTER_API_KEY, system, prompt, Msg)
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        return None


def _escalate(eid: str, question: str) -> None:
    did = store.create_decision(eid, "escalation", question, ["Approve", "Decline"], {})
    store.update_event(eid, status="needs_human")
    _wait_answer(eid, did)
    dec = store.get_decision(did)
    ans = dec["status"] if dec else "declined"
    store.add_turn(eid, "system", "coordinator", f"Coordinator: {ans}")
    store.update_event(eid, status="resolved",
                       outcome=f"Escalated to coordinator; answer: {ans}")


def _decision_kind(card: TriageCard) -> str:
    if card.category == "staffing":
        return "volunteer_conflict"
    if card.event_type == "surge_need":
        return "surge_commit"
    return "budget_spend"


def _record_impact(eid: str, event: dict, done_msg: Msg) -> None:
    """Ledger entries derived from what was arranged."""
    p = event.get("payload", {})
    kg = float(p.get("quantity_kg") or p.get("kg") or 0)
    if kg:
        store.ledger_add(eid, "kg_saved", kg, done_msg.message[:120])
        store.ledger_add(eid, "meals", round(kg * 1.2), f"~{kg} kg rescued (1.2 meals/kg)")
        store.ledger_add(eid, "usd_value", round(kg * 2.8, 2), f"est. retail value of {kg} kg")


def _wait_answer(eid: str, did: str, timeout_s: float = 3600.0) -> str | None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        d = store.get_decision(did)
        if d and d["status"] in {"approved", "declined"}:
            return d["status"]
        time.sleep(1.0)
    return None


def _turns_text(eid: str, last: int = 12) -> str:
    lines = []
    for t in store.list_turns(eid)[-last:]:
        fields = f" | {t['fields']}" if t["fields"] else ""
        lines.append(f"{t['side']} ({t['intent']}): {t['message'][:260]}{fields}")
    return "\n".join(lines) or "(none)"


def _roster_text() -> str:
    lines = []
    for a in store.list_actors():
        lines.append(f"- {a['id']}: {a['name']} ({a['kind']}) state={a['state']}")
    return "\n".join(lines)


def _last_open_question(eid: str) -> str:
    turns = store.list_turns(eid)
    for t in reversed(turns):
        if t["side"].startswith("actor"):
            return f"Last word from {t['side']}: {t['message'][:200]}"
    return "No actor replies yet."
