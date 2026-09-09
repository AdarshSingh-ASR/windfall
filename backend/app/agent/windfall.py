"""Windfall's triage + pricing graph (Strands multiagent Graph).

intake -> research -> price. The price node emits the OpportunityMatch:
kind, value band, deadline pressure, confidence, and whether the human's
consent is needed before filing. Real Strands Graph, one resilient call per node.
"""
from __future__ import annotations

import json

from strands import Agent
from strands.multiagent import GraphBuilder

from ..config import HOUSEHOLD, WINDFALL_MODEL
from ..protocol import OpportunityMatch
from .research import web_search
from .resilience import chat

INTAKE_PROMPT = """You are Windfall's intake agent. Extract the hard facts of the incoming
money opportunity: what it is, who issues it, the exact amount or formula, the deadline,
and what a claimant must provide. Terse and concrete."""

RESEARCH_PROMPT = """You are Windfall's research agent. Given the opportunity facts, use the
web_search tool once if a regulation, program rule, or dollar band matters; otherwise answer
from knowledge. State: the rule that makes the claim valid, the realistic dollar range, and
the one thing that usually gets such claims denied. Under 120 words. Do not invent programs."""

PRICE_PROMPT = """You are Windfall's pricing agent. Score the opportunity EXACTLY AS GIVEN against
the household profile and emit the OpportunityMatch. The event_id MUST be exactly: {event_id}
Classify the kind faithfully from the event details — do not invent a different
opportunity (if the event says utility discount, kind=discount_program; a flight delay is
refund_rule; dormant accounts are unclaimed_property; court settlements are settlement).
Confidence reflects eligibility certainty (1.0 = airtight, rule cites the household's exact
situation). needs_consent is TRUE whenever filing requires an SSN, signature, a legal opt-in
decision, or a class-action election — FALSE for routine utility/portal filings using data
already on file. est_value_low is the conservative number; est_value_high the optimistic one."""


def run_triage_graph(event: dict) -> tuple[OpportunityMatch, str]:
    def _agent(name: str, prompt: str, **kw) -> Agent:
        return Agent(name=name, model=_model(), system_prompt=prompt,
                     callback_handler=None, **kw)

    intake = _agent("intake", INTAKE_PROMPT)
    research = _agent("research", RESEARCH_PROMPT, tools=[web_search])
    price = _agent("price", PRICE_PROMPT.format(event_id=event["id"]))

    builder = GraphBuilder()
    builder.add_node(intake, "intake")
    builder.add_node(research, "research")
    builder.add_node(price, "price")
    builder.add_edge("intake", "research")
    builder.add_edge("research", "price")
    builder.set_entry_point("intake")
    builder.set_execution_timeout(600)
    builder.set_max_node_executions(12)
    graph = builder.build()

    task = (
        f"OPPORTUNITY ({event['kind']} from {event['source']}): {event['title']}\n"
        f"DETAILS: {json.dumps(event['payload'])}\n\n"
        f"HOUSEHOLD PROFILE: {json.dumps(HOUSEHOLD)}\n\n"
        "1. intake: extract the facts. 2. research: the governing rule and dollar band "
        "(search only if a rule/band matters). 3. price: produce the OpportunityMatch as your JSON answer."
    )
    result = graph(task)

    research_text, match = "", None
    for node in result.execution_order:
        text = str(node.result.result)
        if node.node_id == "research":
            research_text = text
        elif node.node_id == "price":
            match = _coerce_match(text, event["id"])
    if match is None:
        raise RuntimeError("price node produced no OpportunityMatch")
    match.event_id = event["id"]  # authoritative
    return match, research_text


def _model():
    from .llm import windfall_model

    return windfall_model()


def _coerce_match(text: str, event_id: str) -> OpportunityMatch | None:
    """Parse the OpportunityMatch out of the price node's answer, with one
    repair pass through a plain completion if the JSON is malformed."""
    import re

    def _try(s: str) -> OpportunityMatch | None:
        m = re.search(r"\{.*\}", s, re.DOTALL)
        if not m:
            return None
        try:
            return OpportunityMatch.model_validate_json(m.group(0))
        except Exception:  # noqa: BLE001
            return None

    match = _try(text)
    if match is not None:
        return match
    try:
        fixed = chat(
            WINDFALL_MODEL, None,
            "Fix this into a single valid JSON object matching an OpportunityMatch: "
            "event_id(str), kind(settlement|benefit_window|discount_program|refund_rule|unclaimed_property), "
            "source(str), headline(<=90 chars), est_value_low(number), est_value_high(number), "
            "deadline(str), confidence(0-1), what_it_takes(str), needs_consent(bool), consent_question(str). "
            "Answer with ONLY the JSON.",
            text[:3000],
        )
        return _try(fixed)
    except Exception:  # noqa: BLE001
        return None
