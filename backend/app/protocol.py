"""Windfall protocol: typed contracts for the found-money pipeline.

FileMove      — what Windfall submits to a clerk (or records internally).
ProgramReply  — what a simulated issuing body answers.
OpportunityMatch — triage output.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class OpportunityMatch(BaseModel):
    """Output of the triage graph for one raw opportunity event."""

    event_id: str
    kind: str = Field(description="settlement | benefit_window | discount_program | refund_rule | unclaimed_property")
    source: str = Field(description="who issues it: utility, court, state comptroller, airline, agency")
    headline: str = Field(description="one line, <=90 chars")
    est_value_low: float = Field(description="conservative dollar estimate")
    est_value_high: float = Field(description="optimistic dollar estimate")
    deadline: str = Field(description="ISO date or 'rolling'")
    confidence: float = Field(ge=0.0, le=1.0, description="eligibility confidence from the household profile")
    what_it_takes: str = Field(description="documents/fields required to claim, 1-2 sentences")
    needs_consent: bool = Field(description="true if human opt-in/SSN/signature is required before filing")
    consent_question: str = Field(default="", description="the one question, if needs_consent")


class FileMove(BaseModel):
    """One filing move by Windfall."""

    intent: str = Field(description="file | supply_info | appeal | done | closed | note")
    message: str = Field(description="the actual submitted text / summary, procedural and exact")
    fields: dict = Field(default_factory=dict, description="form fields, amounts, references")


class ProgramReply(BaseModel):
    """What an issuing body's clerk-agent answers."""

    status: str = Field(description="accepted | needs_more_info | denied | approved")
    message: str = Field(description="2-3 sentences, in character, referencing their own rules")
    fields: dict = Field(default_factory=dict, description="reference numbers, amounts, next steps")
    appealable: bool = Field(default=False, description="does their own policy allow an appeal?")
