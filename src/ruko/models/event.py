"""The structured view of one decision: signals and the ``DecisionEvent``."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, computed_field, model_validator

from ruko.models.common import (
    Action,
    Certainty,
    DecisionStage,
    Dimension,
    EvidenceSpan,
    FundingSource,
    HoldingIntent,
    PaymentDestination,
    PlanHorizon,
    ProductClass,
    ReasonCode,
    SignalSource,
    SourceType,
    StrictModel,
    dimension_of,
)

EventField = Literal[
    "stage",
    "amount_inr",
    "funding_source",
    "product_class",
    "action",
    "source_type",
    "payment_destination",
    "plan",
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

    @computed_field  # type: ignore[prop-decorator]
    @property
    def dimension(self) -> Dimension:
        """Content (about the message) or behavioural (about this user's decision)."""
        return dimension_of(self.code)


class DecisionPlan(StrictModel):
    """The user's own decision plan, summarised.

    The plan itself (the user's words) stays on the device. The server only learns which
    parts exist, which is all it needs to judge completeness. Ruko never writes the plan.
    """

    reason_given: bool = Field(default=False, description="The user wrote why they decide this.")
    horizon: PlanHorizon | None = Field(default=None, description="How long they mean to stay in.")
    reconsider_condition_given: bool = Field(
        default=False, description="The user wrote when they would reconsider or get out."
    )
    matches_prior_plan: bool | None = Field(
        default=None, description="The device says this follows a plan logged earlier."
    )

    @property
    def complete(self) -> bool:
        """True when reason, horizon and reconsider condition are all present."""
        return self.reason_given and self.horizon is not None and self.reconsider_condition_given

    @property
    def started(self) -> bool:
        """True when at least one part of the plan is present."""
        return self.reason_given or self.horizon is not None or self.reconsider_condition_given


class StageResult(StrictModel):
    """The decision stage of an input, how sure Ruko is, and who decided it."""

    stage: DecisionStage = Field(description="Decision stage.")
    confidence: float = Field(ge=0.0, le=1.0, description="0..1; low confidence means unknown.")
    source: Literal["lexicon", "llm", "user", "default"] = Field(description="Who decided.")


class DecisionEvent(StrictModel):
    """Everything the safety engine needs to know about one decision.

    ``amount_inr`` and ``funding_source`` come only from the user (a form field or an
    answer to a clarifying question). Ruko never infers them from a message.
    """

    is_financial_decision: bool = Field(
        description="False if the shared content is not about putting money somewhere."
    )
    stage: DecisionStage = Field(
        default=DecisionStage.CONSIDER_ACTION, description="Decision stage of this input."
    )
    action: Action = Field(default=Action.UNKNOWN, description="What the user means to do.")
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
    plan: DecisionPlan | None = Field(
        default=None, description="Summary of the user's own decision plan; None = not given."
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
