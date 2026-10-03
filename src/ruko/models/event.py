"""The structured view of one decision: signals and the ``DecisionEvent``."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from ruko.models.common import (
    Certainty,
    EvidenceSpan,
    FundingSource,
    HoldingIntent,
    PaymentDestination,
    ProductClass,
    ReasonCode,
    SignalSource,
    SourceType,
    StrictModel,
)

EventField = Literal[
    "amount_inr",
    "funding_source",
    "product_class",
    "source_type",
    "payment_destination",
    "has_exit_plan",
    "holding_intent",
]


class Signal(StrictModel):
    """One observed pattern, always with a certainty label. Never a verdict."""

    code: ReasonCode = Field(description="Which reason this signal supports.")
    certainty: Certainty = Field(description="possible / likely / unclear. Never 'certain'.")
    source: SignalSource = Field(description="Which component produced it.")
    evidence: EvidenceSpan | None = Field(
        default=None, description="Supporting span of the redacted input, if any."
    )


class DecisionEvent(StrictModel):
    """Everything the safety engine needs to know about one decision.

    ``amount_inr`` and ``funding_source`` come only from the user (a form field or an
    answer to a clarifying question). Ruko never infers them from a message.
    """

    is_financial_decision: bool = Field(
        description="False if the shared content is not about putting money somewhere."
    )
    product_class: ProductClass = Field(
        default=ProductClass.UNKNOWN, description="Broad class of the product."
    )
    amount_inr: int | None = Field(
        default=None, ge=1, description="Amount in whole rupees, declared by the user only."
    )
    funding_source: FundingSource = Field(
        default=FundingSource.UNKNOWN, description="Where the money comes from (user-declared)."
    )
    protected_goal_id: str | None = Field(
        default=None,
        max_length=40,
        description="Which protected goal the money is from, when funding is protected_goal.",
    )
    source_type: SourceType = Field(
        default=SourceType.UNKNOWN, description="Who or what prompted the decision."
    )
    payment_destination: PaymentDestination = Field(
        default=PaymentDestination.UNKNOWN, description="Where money would be sent."
    )
    holding_intent: HoldingIntent = Field(
        default=HoldingIntent.UNKNOWN, description="Intended holding period (cost/tax cards only)."
    )
    has_exit_plan: bool | None = Field(
        default=None, description="Whether the user has an exit plan; None = not stated."
    )
    plan_id: str | None = Field(
        default=None,
        max_length=40,
        description="ID of a plan the user logged in advance that this decision follows.",
    )
    signals: list[Signal] = Field(default_factory=list, description="Observed signals.")
    missing_fields: list[EventField] = Field(
        default_factory=list, description="Fields the engine needs that are still unknown."
    )
    field_confidence: dict[EventField, Certainty] = Field(
        default_factory=dict, description="Certainty per extracted field."
    )

    @model_validator(mode="after")
    def _goal_needs_goal_funding(self) -> DecisionEvent:
        if self.protected_goal_id and self.funding_source != FundingSource.PROTECTED_GOAL:
            raise ValueError("protected_goal_id requires funding_source=protected_goal")
        return self

    def signal_codes(self) -> set[ReasonCode]:
        """Return the set of reason codes present in the signals."""
        return {signal.code for signal in self.signals}
