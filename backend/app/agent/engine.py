"""The Windfall engine: opportunity in -> triage -> claim pipeline -> dollars.

For each opportunity:
  1. triage graph -> OpportunityMatch (kind, value band, confidence, consent?)
  2. if needs_consent: Decision card; block until the human answers
  3. assemble the claim and file it with the issuing body's clerk-agent
  4. clerk accepts / asks for more info / denies
  5. denial with appealable=true -> Windfall drafts and files an appeal
     (one shot; the clerk's appeal ruling is final)
  6. approved dollars go to the Found-Money ledger

Quiet by design: the human is pinged only for consent, opt-ins, postage.
"""
from __future__ import annotations

import threading
import time
import traceback

from .. import store
from ..config import HOUSEHOLD, PACE_S, WINDFALL_MODEL
from ..protocol import FileMove, OpportunityMatch, ProgramReply
from .clerks import clerk_reply
from .resilience import call_with_retry, structured
from .windfall import run_triage_graph

_running: set[str] = set()
_lock = threading.Lock()
_sem = threading.BoundedSemaphore(2)

CLAIM_PROMPT = """You are Windfall, an agent that files claims for money people are owed.

THE OPPORTUNITY: {headline}
WHAT IT TAKES: {takes}

HOUSEHOLD PROFILE (claimant data on file):
{household}

RESEARCH: {research}

You now file the claim. Rules:
- Assemble the claim packet from the profile: include ONLY fields the claim
  actually needs; reference what's on file, never invent documents.
- The profile is COMPLETE for these programs — before declaring anything
  impossible, re-read documents_on_file. An RPL account statement IS a named
  account proof. If the clerk asks for something the profile has, supply it
  (intent=supply_info) with the exact document/reference name.
- One move per step (max 5 steps total).
- intent: file | supply_info | appeal | done | closed | note
- In `message` write the actual text of what you submit — procedural, exact,
  confident. Put form fields in `fields`.
- When the clerk approves, reply intent=done with the amount and reference.
- If denied and appealable=true, file an appeal that cites the specific rule
  or fact the denial overlooked — one precise paragraph, not a rant.
- If denied and NOT appealable AND you have truly exhausted the profile,
  reply intent=closed with the reason. Never close while a document on file
  remains unsupplied.
"""

APPEAL_PROMPT = """You are Windfall's appeals specialist. The first filing was denied.

DENIAL: {denial}

THE CLAIM FILE: {claim}

THE RULE IN THE CLAIMANT'S FAVOR: {rule}

Write the appeal as the actual submission text: cite the specific rule or
record fact the clerk overlooked, attach the missing element from the
household profile if one exists, and request specific relief. One tight
paragraph. Then give the structured reply the appeals desk will receive."""


def start_opportunity(oid: str) -> None:
    with _lock:
        if oid in _running:
            return
        _running.add(oid)
    threading.Thread(target=_run, args=(oid,), daemon=True).start()


def _run(oid: str) -> None:
    try:
        with _sem:
            _run_locked(oid)
    except Exception as exc:  # noqa: BLE001
        store.update_opportunity(oid, status="failed", outcome=f"Engine failure: {exc}")
        store.add_turn(oid, "system", "error", f"Engine failure: {exc}")
        traceback.print_exc()
    finally:
        with _lock:
            _running.discard(oid)


def _run_locked(oid: str) -> None:
    event = store.get_opportunity(oid)
    if not event:
        return

    store.update_opportunity(oid, status="working")
    store.add_turn(oid, "system", "phase", "Scouting: intake -> research -> price")

    match, research_text = call_with_retry(run_triage_graph, event)
    store.update_opportunity(
        oid, triage=match.model_dump(), status="triaged",
        est_low=match.est_value_low, est_high=match.est_value_high,
    )
    store.add_turn(oid, "system", "triage",
                   f"{match.headline} — {match.what_it_takes}",
                   {"kind": match.kind, "confidence": match.confidence,
                    "est_low": match.est_value_low, "est_high": match.est_value_high,
                    "deadline": match.deadline})

    if match.needs_consent and match.consent_question:
        did = store.create_decision(
            oid, "consent", match.consent_question,
            {"match": match.model_dump(), "research": research_text[:800]},
        )
        store.update_opportunity(oid, status="needs_consent")
        answer = _wait_answer(oid, did)
        if answer is None:
            store.update_opportunity(oid, status="failed", outcome="consent timed out")
            return
        dec = store.get_decision(did)
        store.add_turn(oid, "system", "claimant",
                       f"Claimant: {answer}{(' — ' + dec['answer_note']) if dec and dec['answer_note'] else ''}")
        if answer == "declined":
            store.update_opportunity(oid, status="resolved",
                                     outcome="Claimant opted out; nothing filed")
            store.add_turn(oid, "system", "closed", "Opted out. Opportunity logged, nothing filed.")
            return

    _file(event, match, research_text)


def _file(event: dict, match: OpportunityMatch, research_text: str) -> None:
    oid = event["id"]
    clerk = store.get_clerk(event["payload"].get("clerk_id", ""))
    if not clerk:
        store.update_opportunity(oid, status="failed", outcome=f"no clerk for {event['source']}")
        store.add_turn(oid, "system", "error", f"No issuing body registered for {event['source']}.")
        return

    steps = 0
    max_steps = 6
    last_reply: ProgramReply | None = None
    claim_desc = "(nothing filed yet — prepare and file the claim)"
    supplied: set[str] = set()  # info elements already given to the clerk

    while steps < max_steps:
        time.sleep(PACE_S)
        steps += 1
        prompt = (
            f"STEP {steps} of {max_steps}.\n"
            f"CLAIM STATE: {claim_desc}\n"
        )
        if last_reply is not None:
            prompt += (
                f"CLERK'S DETERMINATION ({clerk['org']}): status={last_reply.status} "
                f"appealable={last_reply.appealable} — {last_reply.message} fields={last_reply.fields}\n"
            )
            if last_reply.status == "needs_more_info":
                prompt += (
                    "The clerk wants more info. Supply exactly what's missing from the profile — "
                    "nothing else. Elements already supplied (do NOT resend): "
                    + (", ".join(sorted(supplied)) if supplied else "(none yet)")
                    + ". If the profile has no document satisfying the request, file an appeal "
                    "citing why the supplied evidence meets the rule's substance.\n"
                )
            elif last_reply.status == "denied" and last_reply.appealable:
                prompt += (
                    f"APPEAL INSTRUCTION: {APPEAL_PROMPT.format(denial=last_reply.message, claim=claim_desc, rule=research_text[:400])}\n"
                )
            elif last_reply.status == "denied":
                prompt += "The denial is final (not appealable). Close the file honestly.\n"
        prompt += "\nYour next move."

        reply = _safe_move(prompt, match, research_text)
        if reply is None:
            break

        if reply.intent == "done":
            store.add_turn(oid, "system", "done", reply.message, reply.fields)
            def _dollars(v) -> float:
                import re as _re
                if isinstance(v, (int, float)):
                    return float(v)
                m = _re.search(r"[\d,]+(?:\.\d+)?", str(v))
                return float(m.group(0).replace(",", "")) if m else match.est_value_low
            amount = _dollars(reply.fields.get("amount", match.est_value_low))
            annual = reply.fields.get("annualized")
            store.ledger_add(oid, f"{event['source']}: {match.headline[:60]}", amount,
                             "recovered" if reply.fields.get("one_time", True) else "annualized")
            if annual:
                store.ledger_add(oid, f"{event['source']}: {match.headline[:60]} (annualized)",
                                 float(annual), "annualized")
            store.update_opportunity(oid, status="approved", outcome=reply.message[:200])
            return
        if reply.intent == "closed":
            store.add_turn(oid, "system", "closed", reply.message)
            store.update_opportunity(oid, status="denied", outcome=reply.message[:200])
            return

        store.add_turn(oid, "windfall", reply.intent, reply.message, reply.fields)
        for k in reply.fields:
            supplied.add(k)
        time.sleep(PACE_S)
        dossier = _file_dossier(oid)
        det = clerk_reply(clerk, reply.message, dossier)
        store.add_turn(oid, f"clerk:{clerk['id']}", det.status, det.message, det.fields)
        last_reply = det
        claim_desc = f"filed via {reply.intent}: {reply.message[:150]}"

    store.update_opportunity(oid, status="awaiting",
                             outcome="Pipeline budget reached; file kept open")
    store.add_turn(oid, "system", "note",
                   "Step budget reached without a determination. Windfall keeps the "
                   "file open and will follow up when the clerk's queue clears.")


def _file_dossier(oid: str) -> str:
    """Everything the clerk must treat as on file: profile + every element
    Windfall has submitted so far. Prevents stateless clerks from re-demanding
    documents that are already in the record."""
    import json as _json

    lines = [f"COMPLETE CASE FILE (everything submitted to date):"]
    lines.append(f"CLAIMANT PROFILE: {_json.dumps(HOUSEHOLD)}")
    for t in store.list_turns(oid):
        if t["side"] == "windfall":
            fields = f" | fields: {_json.dumps(t['fields'])}" if t["fields"] else ""
            lines.append(f"- SUBMITTED ({t['intent']}): {t['message'][:180]}{fields}")
    return "\n".join(lines)


def _safe_move(prompt: str, match: OpportunityMatch, research_text: str) -> FileMove | None:
    system = CLAIM_PROMPT.format(
        headline=match.headline,
        takes=match.what_it_takes,
        household=__import__("json").dumps(HOUSEHOLD, indent=1),
        research=research_text[:500],
    )
    try:
        return structured(WINDFALL_MODEL, None, system, prompt, FileMove)
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        return None


def _wait_answer(oid: str, did: str, timeout_s: float = 3600.0) -> str | None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        d = store.get_decision(did)
        if d and d["status"] in {"approved", "declined"}:
            return d["status"]
        time.sleep(1.0)
    return None
