"""Shared structured vocabulary: the TriageCard protocol.

Every event Gleaner handles is triaged into one of these before anything
runs. Every stakeholder message uses Msg. Decisions use Decision. This is
the whole contract between the UI, the engine, and the agents.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class TriageCard(BaseModel):
    """The output of the triage graph for one event."""

    event_id: str
    event_type: str = Field(description="donation_offer | surge_need | volunteer_cancel | logistics | info")
    urgency: int = Field(ge=1, le=5, description="1 = routine, 5 = critical right now")
    category: str = Field(description="food_safety | matching | staffing | logistics | recognition | general")
    headline: str = Field(description="one line, <=90 chars")
    action_plan: str = Field(description="what Gleaner will do, 1-3 sentences")
    needs_human: bool = Field(description="true ONLY if policy/dignity/judgment requires the coordinator")
    human_question: str = Field(default="", description="the one question for the human, if needs_human")
    ttl_note: str = Field(default="", description="when this goes stale, if ever")


class Msg(BaseModel):
    """One stakeholder turn in a conversation Gleaner conducts."""

    to: str = Field(description="actor id, e.g. donor-1")
    intent: str = Field(description="ask | offer | confirm | decline | reroute | thank | update")
    message: str = Field(description="1-3 sentences, warm, in character")
    fields: dict = Field(default_factory=dict, description="structured payload (quantities, times, ids)")


class ActorReply(BaseModel):
    """What a simulated stakeholder answers."""

    accept: bool
    message: str = Field(description="1-2 sentences in character")
    fields: dict = Field(default_factory=dict)


class Decision(BaseModel):
    """A human gate record."""

    id: str
    event_id: str
    kind: str = Field(description="surge_commit | surplus_redirect | budget_spend | volunteer_conflict")
    question: str
    options: list[str] = Field(default_factory=list)
    context: dict = Field(default_factory=dict)
    status: str = Field(default="pending", description="pending | approved | declined")
    answer_note: str = Field(default="")


def describe_card(c: TriageCard) -> str:
    return f"[{c.event_type} u{c.urgency}] {c.headline} -> {c.action_plan}"
