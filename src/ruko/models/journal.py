"""Journal entries. The journal lives on the device; the server only computes patterns."""

from __future__ import annotations

import datetime as dt
from enum import StrEnum
from typing import Literal

from pydantic import Field

from ruko.models.common import InterventionLevel, ProductClass, ReasonCode, SourceType, StrictModel
from ruko.models.responses import ResponseMeta, TemplateRef


class JournalAction(StrEnum):
    """What the user did after the pause."""

    WENT_AHEAD = "went_ahead"
    WAITED = "waited"
    DROPPED = "dropped"


class JournalOutcome(StrEnum):
    """Outcome the user logged later (optional)."""

    GAIN = "gain"
    LOSS = "loss"
    FLAT = "flat"
    UNKNOWN = "unknown"


class JournalEntry(StrictModel):
    """One decision as recorded on the device."""

    id: str = Field(min_length=1, max_length=40, description="Device-generated entry ID.")
    date: dt.date = Field(description="Date of the decision.")
    product_class: ProductClass = Field(description="Product class.")
    amount_inr: int | None = Field(default=None, ge=1, description="Amount, if logged.")
    source_type: SourceType = Field(description="What prompted the decision.")
    level_shown: InterventionLevel = Field(description="Intervention level Ruko showed.")
    reason_codes: list[ReasonCode] = Field(default_factory=list, description="Reasons shown.")
    action: JournalAction = Field(description="What the user did.")
    overrode: bool = Field(
        default=False, description="True if the user continued past an L2/L3 intervention."
    )
    followed_own_rules: bool = Field(description="True if no personal rule was breached.")
    exit_plan_set: bool = Field(description="True if an exit plan was written.")
    exit_plan_followed: bool | None = Field(
        default=None, description="Logged later: was the exit plan followed? None = not yet."
    )
    outcome: JournalOutcome | None = Field(default=None, description="Logged later, optional.")


TrendDirection = Literal["falling", "rising", "steady", "not_enough_data"]


class WeekPoint(StrictModel):
    """Interventions per decision for one week (Monday start)."""

    week_start: dt.date = Field(description="Monday of the week.")
    decisions: int = Field(ge=0, description="Decisions journaled that week.")
    interventions: int = Field(ge=0, description="Decisions where Ruko stepped in (L1-L3).")
    per_decision: float = Field(ge=0, description="interventions / decisions.")


class JournalReviewResponse(StrictModel):
    """The user's own patterns: numbers and rendered template text only. Nothing is stored."""

    kind: Literal["journal_review"] = "journal_review"
    as_of: dt.date = Field(description="Review date; entries after it are ignored.")
    total_decisions: int = Field(ge=0, description="Entries considered.")
    tip_driven_pct: float | None = Field(
        default=None, description="% of decisions that started from a group tip or influencer."
    )
    rules_followed_pct: float | None = Field(
        default=None, description="% of decisions within the user's own rules."
    )
    exit_plan_set_pct: float | None = Field(default=None, description="% with an exit plan.")
    exit_plan_followed_pct: float | None = Field(
        default=None, description="% of logged exit plans that were followed."
    )
    exit_plans_pending: int = Field(default=0, ge=0, description="Exit plans not yet logged.")
    pauses: int = Field(default=0, ge=0, description="Decisions with an L2/L3 pause.")
    overrides: int = Field(default=0, ge=0, description="Pauses the user continued past.")
    weekly: list[WeekPoint] = Field(default_factory=list, description="Weekly trend points.")
    trend: TrendDirection = Field(description="Direction of interventions per decision.")
    highlights: list[str] = Field(default_factory=list, description="Rendered highlights.")
    speak: list[TemplateRef] = Field(default_factory=list, description="What /v1/speak reads.")
    meta: ResponseMeta = Field(description="Metadata.")
