"""Gleaner's triage + planning graph (Strands multiagent Graph).

intake -> research -> plan, as a real Strands Graph. Each node is one
resilient LLM call; the plan node emits the TriageCard that decides
everything: what Gleaner does on its own, and whether the human is pinged.
"""
from __future__ import annotations

import json

from strands import Agent
from strands.multiagent import GraphBuilder

from ..config import GLEANER_MODEL, OPENROUTER_API_KEY
from ..protocol import TriageCard
from .research import web_search
from .resilience import structured

INTAKE_PROMPT = """You are Gleaner's intake agent for the Riverside Food Network.
Extract the hard facts of the incoming event: what is offered or needed, quantities,
deadlines, and which roster actors are relevant. Be terse and concrete."""

RESEARCH_PROMPT = """You are Gleaner's research agent. Given the event facts, use the
web_search tool once if food-safety or compliance rules matter; otherwise answer from
knowledge. State: the key constraint or leverage, and what usually works in this situation.
Under 120 words. Note: mixed produce does NOT require refrigerated transport — insulated
crates are fine for same-day runs. Do not invent requirements the roster cannot meet."""

PLAN_PROMPT = """You are Gleaner's planning agent for the Riverside Food Network.
The TriageCard's event_id MUST be exactly: {event_id}
Gleaner handles routine coordination AUTONOMOUSLY: matching surplus to pantries, rerouting
when storage is short, confirming pickups, thanking donors. It pings the human coordinator
ONLY for real judgment calls:
- spending money (vouchers, truck rental, emergency buy)
- committing the network to a partner commitment it can't quietly undo
- dignity/policy calls (what may be served, who gets prioritized)
- conflicts between stakeholders that niceness can't solve

Decide: urgency (1-5), what Gleaner will DO on its own, and whether the human is needed.
A good action_plan names the specific actors and the sequence. needs_human is FALSE for
anything routine — matching, rerouting, confirming, thanking are all routine here.
Routing facts: the Regional Food Bank needs 24h notice for big loads, so same-day volume
goes to St. Mary's Community Kitchen (kitchen-marys, 300 kg walk-in) or Hope Pantry
(pantry-hope, 25 kg left). Volunteers: Jun covers weekday afternoons, Marco mornings,
Priya evenings after 18:00."""


def run_triage_graph(event: dict) -> tuple[TriageCard, str]:
    """Runs intake -> research -> plan as a Strands Graph.
    Returns (triage_card, research_text)."""
    def _agent(name: str, prompt: str, **kw) -> Agent:
        return Agent(name=name, model=_model(), system_prompt=prompt,
                     callback_handler=None, **kw)

    intake = _agent("intake", INTAKE_PROMPT)
    research = _agent("research", RESEARCH_PROMPT, tools=[web_search])
    plan = _agent("plan", PLAN_PROMPT.format(event_id=event["id"]))

    builder = GraphBuilder()
    builder.add_node(intake, "intake")
    builder.add_node(research, "research")
    builder.add_node(plan, "plan")
    builder.add_edge("intake", "research")
    builder.add_edge("research", "plan")
    builder.set_entry_point("intake")
    builder.set_execution_timeout(600)
    builder.set_max_node_executions(12)
    graph = builder.build()

    roster_lines = "\n".join(
        f"- {a['id']}: {a['name']} ({a['kind']}) state={json.dumps(a['state'])}"
        for a in store_list_actors()
    )
    task = (
        f"EVENT ({event['kind']}): {event['title']}\n"
        f"DETAILS: {json.dumps(event['payload'])}\n\n"
        f"ROSTER (id: name — current state):\n{roster_lines}\n\n"
        "1. intake: extract the facts. 2. research: the key constraint (search only if "
        "food-safety/compliance matters). 3. plan: produce the TriageCard as your JSON answer."
    )
    result = graph(task)

    research_text, card = "", None
    for node in result.execution_order:
        text = str(node.result.result)
        if node.node_id == "research":
            research_text = text
        elif node.node_id == "plan":
            card = _coerce_card(text, event["id"])
    if card is None:
        raise RuntimeError("plan node produced no TriageCard")
    card.event_id = event["id"]  # authoritative
    return card, research_text


def _model():
    # lazy import to share the cached LiteLLMModel
    from .llm import gleaner_model

    return gleaner_model()


def store_list_actors():
    from .. import store

    return store.list_actors()


def _coerce_card(text: str, event_id: str) -> TriageCard | None:
    """Parse a TriageCard out of the plan node's answer. The graph node runs
    free-form, so the card may be wrapped in prose or fenced blocks; if the
    JSON is malformed, one repair pass asks the model to fix it."""
    import re

    from .resilience import chat

    def _try(s: str) -> TriageCard | None:
        m = re.search(r"\{.*\}", s, re.DOTALL)
        if not m:
            return None
        try:
            return TriageCard.model_validate_json(m.group(0))
        except Exception:  # noqa: BLE001
            return None

    card = _try(text)
    if card is not None:
        return card
    # repair pass
    try:
        from ..config import GLEANER_MODEL, OPENROUTER_API_KEY

        fixed = chat(
            GLEANER_MODEL, OPENROUTER_API_KEY or None,
            "Fix this into a single valid JSON object matching a TriageCard: "
            "event_id(str), event_type(donation_offer|surge_need|volunteer_cancel|logistics|info), "
            "urgency(int 1-5), category(food_safety|matching|staffing|logistics|recognition|general), "
            "headline(<=90 chars), action_plan(str), needs_human(bool), human_question(str), ttl_note(str). "
            "Answer with ONLY the JSON.",
            text[:3000],
        )
        return _try(fixed)
    except Exception:  # noqa: BLE001
        return None


def _model_id() -> str:
    from ..config import GLEANER_MODEL

    return GLEANER_MODEL
