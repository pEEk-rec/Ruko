"""Journal entries and the journal review. The journal lives on the device.

The server only computes the user's own patterns for one request (``docs/impact_metrics.md``)
and keeps nothing.
"""

from __future__ import annotations

import datetime as dt
from enum import StrEnum
from typing import Literal

from pydantic import Field

from ruko.models.common import (
    DecisionStage,
    InterventionLevel,
    ProductClass,
    ReasonCode,
    SourceType,
    StrictModel,
)
from ruko.models.event import DecisionPlan
from ruko.models.responses import ResponseMeta, TemplateRef


class JournalAction(StrEnum):
    """What the user did after Ruko showed the decision (always their choice)."""

    WENT_AHEAD = "went_ahead"
    CHANGED_AMOUNT = "changed_amount"
    DELAYED = "delayed"
    SET_PLAN = "set_plan"
    DROPPED = "dropped"


RECONSIDERED = frozenset(
    {JournalAction.CHANGED_AMOUNT, JournalAction.DELAYED, JournalAction.SET_PLAN,
     JournalAction.DROPPED}
)  # fmt: skip
"""Actions that count as reconsidering after a pause."""


class JournalOutcome(StrEnum):
    """Outcome the user logged later (optional)."""

    GAIN = "gain"
    LOSS = "loss"
    FLAT = "flat"
    UNKNOWN = "unknown"


class JournalEntry(StrictModel):
    """One decision as recorded on the device. Free text stays on the device."""

    id: str = Field(min_length=1, max_length=40, description="Device-generated entry ID.")
    date: dt.date = Field(description="Date of the decision.")
    stage: DecisionStage = Field(
        default=DecisionStage.CONSIDER_ACTION, description="Decision stage at the time."
    )
    product_class: ProductClass = Field(description="Product class.")
    amount_inr: int | None = Field(default=None, ge=1, description="Amount, if logged.")
    source_type: SourceType = Field(description="What prompted the decision.")
    level_shown: InterventionLevel = Field(description="Intervention level Ruko showed.")
    reason_codes: list[ReasonCode] = Field(default_factory=list, description="Reasons shown.")
    action: JournalAction = Field(description="What the user did.")
    overrode: bool = Field(
        default=False, description="True if the user continued past an L2/L3 pause."
    )
    override_reason_given: bool = Field(
        default=False, description="True if the user wrote a reason for continuing."
    )
    pause_completed: bool | None = Field(
        default=None, description="True if the user read the pause through; None = no pause."
    )
    could_state_why: bool | None = Field(
        default=None, description="The user could say why the pause appeared (comprehension)."
    )
    followed_own_rules: bool = Field(description="True if no personal rule was breached.")
    plan: DecisionPlan | None = Field(default=None, description="Which plan parts were written.")
    plan_followed: bool | None = Field(
        default=None, description="Logged later: was the plan followed? None = not yet."
    )
    own_rules_count: int | None = Field(
        default=None, ge=0, le=100, description="How many own rules the user had written then."
    )
    own_plans_count: int | None = Field(
        default=None, ge=0, le=1000, description="How many plans the user had written then."
    )
    outcome: JournalOutcome | None = Field(default=None, description="Logged later, optional.")


Trend = Literal["growing", "steady", "shrinking", "not_enough_data"]


class WeekPoint(StrictModel):
    """Interventions per decision for one week (Monday start). Shown, not scored."""

    week_start: dt.date = Field(description="Monday of the week.")
    decisions: int = Field(ge=0, description="Decisions journaled that week.")
    interventions: int = Field(ge=0, description="Decisions where Ruko stepped in (L1-L3).")
    per_decision: float = Field(ge=0, description="interventions / decisions.")


class JournalReviewResponse(StrictModel):
    """The user's own patterns (docs/impact_metrics.md): numbers and rendered text only.

    A falling number of interventions is shown but never treated as success on its own:
    it can also mean Ruko became less sensitive.
    """

    kind: Literal["journal_review"] = "journal_review"
    as_of: dt.date = Field(description="Review date; entries after it are ignored.")
    total_decisions: int = Field(ge=0, description="Entries considered.")
    unsolicited_share_pct: float | None = Field(
        default=None, description="% of decisions that started from a group tip or influencer."
    )
    plans_set_pct: float | None = Field(default=None, description="% with a written plan.")
    plans_followed_pct: float | None = Field(
        default=None, description="% of plans the user followed (where they logged it)."
    )
    plans_pending: int = Field(default=0, ge=0, description="Plans whose result is not logged.")
    pauses: int = Field(default=0, ge=0, description="Decisions with an L2/L3 pause.")
    pause_completion_pct: float | None = Field(
        default=None, description="% of pauses the user read through."
    )
    comprehension_pct: float | None = Field(
        default=None, description="% of pauses where the user could say why it appeared."
    )
    reconsideration_pct: float | None = Field(
        default=None, description="% of pauses after which the user changed, delayed or planned."
    )
    overrides_with_reason: int = Field(default=0, ge=0, description="Continued, with a reason.")
    overrides_without_reason: int = Field(default=0, ge=0, description="Continued, no reason.")
    own_rules_first: int | None = Field(default=None, description="Own rules at the start.")
    own_rules_latest: int | None = Field(default=None, description="Own rules now.")
    rule_articulation: Trend = Field(description="Are the user's own rules and plans growing?")
    weekly: list[WeekPoint] = Field(default_factory=list, description="Interventions per week.")
    highlights: list[str] = Field(default_factory=list, description="Rendered highlights.")
    speak: list[TemplateRef] = Field(default_factory=list, description="What /v1/speak reads.")
    meta: ResponseMeta = Field(description="Metadata.")
