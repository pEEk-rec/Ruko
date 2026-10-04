"""The minimal user snapshot the device sends with each request.

The profile lives on the user's device. The server uses it for one request and
keeps nothing. Sensitive amounts are sent as bands by default; the device may send
an exact figure instead if the user chose to enter one.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from ruko.models.common import PlanHorizon, ProductClass, StrictModel

ExpenseBand = Literal["lt_10k", "10k_25k", "25k_50k", "50k_1l", "1l_2l", "gt_2l"]
"""Monthly expenses bands in rupees (bounds live in data/policy/intervention.yaml)."""

SavingsBand = Literal["lt_25k", "25k_1l", "1l_3l", "3l_10l", "10l_25l", "gt_25l"]
"""Liquid savings bands in rupees (bounds live in data/policy/intervention.yaml)."""

AgeBand = Literal["lt_30", "30_40", "40_50", "50_60", "gt_60"]
"""Age bands, matching the bands SEBI uses in its derivatives study."""

TradesPerWeekBand = Literal["0", "1_5", "6_20", "gt_20"]
"""Self-declared number of trades in the last 7 days."""


class Experience(StrEnum):
    """Self-declared experience with a product class."""

    NONE = "none"
    SOME = "some"
    REGULAR = "regular"


class ProtectedGoal(StrictModel):
    """Money the user has set aside for something that must not be put at risk."""

    id: str = Field(min_length=1, max_length=40, description="Device-generated goal ID.")
    amount_inr: int | None = Field(
        default=None, ge=0, description="Amount set aside for the goal, if the user entered it."
    )


class UserRules(StrictModel):
    """Rules the user wrote for themselves while calm. Ruko only reflects them back."""

    max_share_of_savings_pct: int | None = Field(
        default=None, ge=1, le=100, description="Max % of liquid savings in one decision."
    )
    max_amount_inr: int | None = Field(
        default=None, ge=1, description="Max rupees in one decision."
    )
    no_borrowed_money: bool = Field(default=False, description="Never invest borrowed money.")
    protected_goals: list[ProtectedGoal] = Field(
        default_factory=list, max_length=10, description="Goals whose money is off-limits."
    )
    cooling_off_minutes: int | None = Field(
        default=None, ge=0, le=1440, description="Wait this long before acting on a tip."
    )


class PlannedDecision(StrictModel):
    """A decision the user planned in advance, while calm (the words stay on the device)."""

    id: str = Field(min_length=1, max_length=40, description="Device-generated plan ID.")
    product_class: ProductClass = Field(description="Product class the plan covers.")
    amount_min_inr: int = Field(ge=0, description="Lower end of the planned amount.")
    amount_max_inr: int = Field(ge=1, description="Upper end of the planned amount.")
    horizon: PlanHorizon | None = Field(default=None, description="Planned horizon.")
    reconsider_condition_given: bool = Field(
        default=False, description="The plan says when the user would reconsider or get out."
    )

    @model_validator(mode="after")
    def _ordered_amounts(self) -> PlannedDecision:
        if self.amount_min_inr > self.amount_max_inr:
            raise ValueError("amount_min_inr must not exceed amount_max_inr")
        return self


class RecentContext(StrictModel):
    """Recent behaviour the user declared. Ruko cannot observe trades itself."""

    post_loss: bool = Field(default=False, description="User says they recently took a loss.")
    late_night: bool = Field(
        default=False,
        description="The device clock says it is late at night where the user is (a clock fact).",
    )
    trades_this_week: TradesPerWeekBand = Field(
        default="0", description="Self-declared trades in the last 7 days."
    )


class AttentionCounts(StrictModel):
    """Interventions shown in the last 7 days, counted on the device."""

    l1_this_week: int = Field(default=0, ge=0, description="L1 nudges shown in 7 days.")
    l2_this_week: int = Field(default=0, ge=0, description="L2 speed bumps shown in 7 days.")
    l3_this_week: int = Field(default=0, ge=0, description="L3 warnings shown in 7 days.")
    rule_following_streak: int = Field(
        default=0, ge=0, description="Consecutive past decisions that followed the user's rules."
    )


class UserProfile(StrictModel):
    """The minimal snapshot sent with a request. Nothing here is stored server-side."""

    monthly_expenses_band: ExpenseBand | None = Field(default=None, description="Expense band.")
    monthly_expenses_inr: int | None = Field(
        default=None, ge=1, description="Exact monthly expenses, only if the user entered it."
    )
    liquid_savings_band: SavingsBand | None = Field(default=None, description="Savings band.")
    liquid_savings_inr: int | None = Field(
        default=None, ge=0, description="Exact liquid savings, only if the user entered it."
    )
    emergency_buffer_months: int | None = Field(
        default=None, ge=0, le=36, description="Months of expenses the user wants kept untouched."
    )
    rules: UserRules = Field(default_factory=UserRules, description="The user's own rules.")
    experience: dict[ProductClass, Experience] = Field(
        default_factory=dict, description="Declared experience per product class."
    )
    age_band: AgeBand | None = Field(default=None, description="Optional age band.")
    recent: RecentContext = Field(default_factory=RecentContext, description="Declared context.")
    plans: list[PlannedDecision] = Field(
        default_factory=list, max_length=20, description="Plans logged in advance."
    )
    seen_card_ids: list[str] = Field(
        default_factory=list, max_length=200, description="Cards already seen and understood."
    )
    seen_lesson_ids: list[str] = Field(
        default_factory=list, max_length=200, description="Lessons already seen (they fade)."
    )
    attention: AttentionCounts = Field(
        default_factory=AttentionCounts, description="Counts for the weekly attention budget."
    )
