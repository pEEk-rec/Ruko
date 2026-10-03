"""The safety engine's output: ``InterventionDecision`` and its parts."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from ruko.models.common import (
    Certainty,
    InterventionLevel,
    ReasonCode,
    Severity,
    SignalSource,
    SourceRef,
    StrictModel,
)


class Reason(StrictModel):
    """One reason behind the level, with its severity and certainty."""

    code: ReasonCode = Field(description="Reason code (see docs/reason_codes.md).")
    severity: Severity = Field(description="Default severity from the policy file.")
    certainty: Certainty = Field(description="How sure Ruko is.")
    source: SignalSource = Field(description="Where the reason came from.")


class NumberRange(StrictModel):
    """A ratio shown as a range, because profiles are usually sent as bands."""

    low: float = Field(ge=0, description="Lower end.")
    high: float = Field(ge=0, description="Upper end (equal to low when exact).")
    typical: float = Field(ge=0, description="Value at the band's typical point; shown as 'about'.")


class MoneyRange(StrictModel):
    """A rupee amount shown as a range (integer rupees)."""

    low: int = Field(description="Lower end in rupees (may be negative = shortfall).")
    high: int = Field(description="Upper end in rupees.")
    typical: int = Field(description="Value at the band's typical point.")


class AdverseMove(StrictModel):
    """Arithmetic illustration: what an X% move against the position means in rupees.

    This is not a prediction; it is multiplication on the user's own amount.
    """

    move_pct: float = Field(gt=0, le=100, description="Size of the illustrative adverse move.")
    loss_inr: int = Field(ge=0, description="Rupee impact of that move on the exposure.")
    exposure_inr: int = Field(ge=0, description="Exposure the illustration is computed on.")
    label: Literal["illustration"] = "illustration"


class ComputedNumbers(StrictModel):
    """Numbers about this decision, in the user's own rupees."""

    amount_inr: int | None = Field(default=None, description="Amount of this decision.")
    basis: Literal["exact", "band", "none"] = Field(
        default="none", description="Whether profile numbers were exact or from bands."
    )
    months_of_expenses: NumberRange | None = Field(
        default=None, description="Amount expressed as months of the user's expenses."
    )
    share_of_savings_pct: NumberRange | None = Field(
        default=None, description="Amount as % of liquid savings."
    )
    remaining_savings_inr: MoneyRange | None = Field(
        default=None, description="Liquid savings left after this decision."
    )
    remaining_buffer_months: NumberRange | None = Field(
        default=None, description="Savings left, in months of expenses."
    )
    adverse_moves: list[AdverseMove] = Field(
        default_factory=list, description="Leverage illustrations (derivatives only)."
    )


class AttentionState(StrictModel):
    """The weekly attention budget for soft nudges."""

    l1_budget_per_week: int = Field(ge=0, description="Max L1 nudges per 7 days.")
    l1_used_this_week: int = Field(ge=0, description="L1 nudges already shown.")
    suppressed_by_budget: bool = Field(description="True if an L1 was silenced by the budget.")


class BaseRateFact(StrictModel):
    """A group statistic from a cited study. Never a prediction for this user."""

    fact_id: str = Field(description="ID in data/facts/base_rates.yaml.")
    group_key: str = Field(description="Which group the statistic describes, e.g. 'age_lt_30'.")
    text_key: str = Field(description="Template key used to render the statement.")
    slots: dict[str, str] = Field(default_factory=dict, description="Values for the template.")
    caveat_key: str = Field(description="Template key for the non-causal, group-only caveat.")
    source: SourceRef = Field(description="Citation with as_of date and verification status.")


class InterventionDecision(StrictModel):
    """What the deterministic engine decided, and why."""

    level: InterventionLevel = Field(description="L0 silent .. L3 cooling-off / strong warning.")
    computed_level: InterventionLevel = Field(
        description="Level before attention-budget and friction-decay adjustments."
    )
    reasons: list[Reason] = Field(default_factory=list, description="Reasons, most severe first.")
    numbers: ComputedNumbers = Field(
        default_factory=ComputedNumbers, description="Personal numbers."
    )
    attention: AttentionState = Field(description="Attention-budget state.")
    decay_applied: bool = Field(
        default=False, description="True if a novelty-only nudge faded due to a good streak."
    )
    matched_plan_id: str | None = Field(default=None, description="Plan this decision follows.")
    cooling_off_minutes: int | None = Field(
        default=None, description="Suggested wait (the user's own rule, or the L3 default)."
    )
    recovery_entry: bool = Field(
        default=False, description="True if 'I already paid' recovery should be offered."
    )
    base_rate: BaseRateFact | None = Field(default=None, description="Relevant group statistic.")
    override_allowed: Literal[True] = Field(
        default=True, description="Always true: the decision is the user's."
    )
    policy_version: str = Field(description="Version of data/policy/intervention.yaml used.")

    @property
    def reason_codes(self) -> list[ReasonCode]:
        """Return reason codes in severity order."""
        return [reason.code for reason in self.reasons]
