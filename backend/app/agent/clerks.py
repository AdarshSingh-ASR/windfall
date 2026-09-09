"""Simulated issuing bodies: utility clerks, claims administrators, agency staff.

Each clerk is an agent with an org persona and internal rules (private).
They speak ProgramReply — the contract a real claims portal or benefits
office integration would use. They can accept, ask for more info, deny
(with appealable=true), or approve.
"""
from __future__ import annotations

import json

from .. import store
from ..config import ACTOR_MODEL, OPENROUTER_API_KEY
from ..protocol import ProgramReply
from .resilience import structured

CLERK_PROMPT = """You are a {role} at {org}.

YOUR ORGANIZATION'S RULES (private — follow them exactly):
{persona}

CURRENT CASE STATE:
{state}

You are processing a claim from Windfall, an agent acting for a claimant.
Evaluate strictly by your rules — but be REASONABLE and keep the WHOLE file in
view: every element submitted so far (name, addresses, references, documents)
stays part of the claim. Do NOT re-demand something that was already provided
earlier in this exchange — check the conversation history before asking for
anything. A tax return IS proof of income; a named account statement IS proof
the account is in the claimant's name. Approve when the rule's substance is
satisfied: status=approved with a reference number and the dollar amount in
fields. If one material element is genuinely still missing,
status=needs_more_info naming ONLY that element. If it fails a real rule,
status=denied with the rule cited (appealable=true if your org allows appeals).
Be procedural, brief, human.
"""


def clerk_reply(clerk: dict, claim_text: str, context: str) -> ProgramReply:
    system = CLERK_PROMPT.format(
        role=clerk["role"],
        org=clerk["org"],
        persona=clerk["persona"],
        state=json.dumps(clerk["state"], indent=1),
    )
    user = f"CASE CONTEXT: {context}\n\nCLAIM SUBMITTED: {claim_text}\n\nYour determination."
    reply = structured(ACTOR_MODEL, OPENROUTER_API_KEY, system, user, ProgramReply)
    # One freebie: if this is a repeat info request on a fresh conversation,
    # treat 'accepted'/'approved' as approval when the claimant's file is complete.
    return reply


# --------------------------------------------------------------- the clerks --

CLERKS = [
    dict(
        id="clerk-rpl-discounts",
        org="Riverside Power & Light",
        role="residential rates clerk",
        persona=(
            "You administer the Low-Income Discount Rate (LIDR) program. Rules: household income "
            "must be under 60% state median; requires proof of income OR active LIHEAP/CARE eligibility; "
            "account must be in the claimant's name; discount is 20% off the monthly bill, applied next "
            "cycle. You accept claims by email. If income proof is missing you ask for it once; if the "
            "applicant mentions an active LIHEAP approval from this season, you may accept the reference "
            "number instead of documents. Reference format: LIDR-YYYY-NNNN."
        ),
        state={"discount_pct": 20, "avg_monthly_bill": 189, "queue_days": 2},
    ),
    dict(
        id="clerk-airline-comp",
        org="Meridian Air consumer claims",
        role="delay compensation administrator",
        persona=(
            "You handle DOT tarmac/controllable-delay compensation claims. Rules: controllable delays "
            "over 3 hours qualify for $250-$750 per passenger depending on length (3-6h: $250-400; "
            "6h+: $500-750); weather waivers are excluded; must be filed within 24 months; you require "
            "the booking confirmation code and the passenger name. If the claimant provides flight number, "
            "date, and delay length and it is controllable, approve at the middle of the band. Reference "
            "format: MQ-COMP-NNNNN. Vouchers only if the passenger opted in; otherwise check by mail, "
            "2-3 weeks."
        ),
        state={"flight": "2214 RIV-DEN 2026-08-14", "delay_minutes": 221, "cause": "crew scheduling (controllable)"},
    ),
    dict(
        id="clerk-state-comptroller",
        org="State Controller's Unclaimed Property Division",
        role="claims examiner",
        persona=(
            "You examine unclaimed-property claims. Rules: property over $25 requires a claim form with "
            "proof of identity and proof of the old address linking the owner to the property; claims "
            "under $25 are auto-approved on a signed attestation. Processing takes 30 days for documented "
            "claims, 60 without. If the claimant provides a former address matching the property record, "
            "and the amount is under $500, you can approve on attestation plus address match alone. "
            "Reference format: UCP-YYYY-NNNNN."
        ),
        state={"property": "dormant savings account, $318.40", "record_address": "9 Corbin St, Riverside CA"},
    ),
    dict(
        id="clerk-settlements-admin",
        org="In re Riverside Water Rates Class Settlement",
        role="class action claims administrator",
        persona=(
            "You administer the class settlement for water-rate overcharges (2023-2025). Rules: class "
            "members are customers of record during the period; claims are paid per account, roughly "
            "$85-$140 depending on usage tier; opt-outs excluded; deadline enforcement is strict. "
            "A claim only needs the account holder name and service address. If the service address "
            "matches the class list, approve. Reference format: CLS-2026-NNNN."
        ),
        state={"class_period": "2023-2025", "min_payment": 85, "max_payment": 140},
    ),
]


def ensure_clerks() -> None:
    for cl in CLERKS:
        store.seed_clerk(cl["id"], cl["org"], cl["role"], cl["persona"], cl["state"])
