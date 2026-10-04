"""Request bodies for the v1 API (see docs/api_contract.md)."""

from __future__ import annotations

import datetime as dt
from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from ruko.models.calculation import CalculationInputs
from ruko.models.common import (
    LOCALE_PATTERN,
    Action,
    DecisionStage,
    FundingSource,
    HoldingIntent,
    InterventionLevel,
    ProductClass,
    ReasonCode,
    SourceType,
    StrictModel,
)
from ruko.models.event import DecisionEvent, DecisionPlan, EventField
from ruko.models.inputs import RawInput
from ruko.models.journal import JournalEntry
from ruko.models.profile import UserProfile
from ruko.models.responses import ExplanationCard, ResponseMeta, TemplateRef


class DecisionAnswers(StrictModel):
    """Facts the user declares about this decision (form fields or clarify answers).

    These always win over anything extracted from the message.
    """

    amount_inr: int | None = Field(default=None, ge=1, description="Amount in whole rupees.")
    funding_source: FundingSource | None = Field(default=None, description="Where money is from.")
    protected_goal_id: str | None = Field(
        default=None, max_length=40, description="Goal ID when funding is protected_goal."
    )
    product_class: ProductClass | None = Field(default=None, description="Override extraction.")
    source_type: SourceType | None = Field(default=None, description="Override extraction.")
    holding_intent: HoldingIntent | None = Field(default=None, description="Intended holding.")
    stage: DecisionStage | None = Field(
        default=None, description="Stage the user chose in the app (wins over detection)."
    )
    action: Action | None = Field(default=None, description="What the user means to do.")
    plan: DecisionPlan | None = Field(
        default=None, description="Summary of the user's own decision plan (presence only)."
    )
    plan_id: str | None = Field(default=None, max_length=40, description="Plan being followed.")
    calculation: CalculationInputs | None = Field(
        default=None, description="Calculator inputs (calculate stage): typed or answered."
    )
    skipped_fields: list[EventField] = Field(
        default_factory=list,
        max_length=7,
        description="Questions the user chose not to answer; Ruko does not ask them again.",
    )


class AnalyzeRequest(StrictModel):
    """Body of ``POST /v1/analyze``: one shared item plus the device snapshot."""

    input: RawInput = Field(description="The shared text, link or base64 image.")
    locale: str | None = Field(
        default=None,
        pattern=LOCALE_PATTERN,
        description="Language for the response. Defaults to the detected language.",
    )
    profile: UserProfile = Field(default_factory=UserProfile, description="Device snapshot.")
    answers: DecisionAnswers = Field(
        default_factory=DecisionAnswers, description="User-declared facts."
    )


AudioFormat = Literal["wav", "mp3", "ogg", "opus", "webm", "m4a", "aac", "flac", "amr"]


class VoiceAnalyzeRequest(StrictModel):
    """Body of ``POST /v1/analyze/voice``. Audio is processed in memory, never stored."""

    audio_base64: str = Field(min_length=4, description="Base64-encoded audio.")
    audio_format: AudioFormat = Field(description="Container/codec of the audio.")
    speech_locale: str | None = Field(
        default=None, pattern=LOCALE_PATTERN, description="Spoken language hint."
    )
    locale: str | None = Field(
        default=None, pattern=LOCALE_PATTERN, description="Language for the response."
    )
    profile: UserProfile = Field(default_factory=UserProfile, description="Device snapshot.")
    answers: DecisionAnswers = Field(
        default_factory=DecisionAnswers, description="User-declared facts."
    )


class CalculateRequest(StrictModel):
    """Body of ``POST /v1/calculate``: the live calculator. Numbers in, arithmetic out."""

    locale: str = Field(pattern=LOCALE_PATTERN, description="Language for the result.")
    inputs: CalculationInputs = Field(description="The calculator and the user's own numbers.")
    profile: UserProfile = Field(
        default_factory=UserProfile, description="Device snapshot (lesson fading only)."
    )


class LearnRequest(StrictModel):
    """Body of ``POST /v1/learn``: the Learn list for this person (nothing is stored)."""

    locale: str = Field(pattern=LOCALE_PATTERN, description="Language for the list.")
    profile: UserProfile = Field(
        default_factory=UserProfile, description="Device snapshot: what was read, experience."
    )


class LessonRequest(StrictModel):
    """Body of ``POST /v1/learn/lesson``: open one lesson."""

    locale: str = Field(pattern=LOCALE_PATTERN, description="Language for the lesson.")
    lesson_id: str = Field(max_length=64, pattern=r"^[a-z0-9_]+$", description="Lesson to open.")
    profile: UserProfile = Field(
        default_factory=UserProfile, description="Device snapshot (what to suggest next)."
    )


class SpeakRequest(StrictModel):
    """Body of ``POST /v1/speak``: template references to read aloud."""

    locale: str = Field(pattern=LOCALE_PATTERN, description="Language to speak.")
    items: list[TemplateRef] = Field(
        default_factory=list, max_length=10, description="Templates to render, filter and speak."
    )
    lesson_id: str | None = Field(
        default=None,
        max_length=64,
        pattern=r"^[a-z0-9_]+$",
        description="Read one lesson (title and body) instead of items.",
    )

    @model_validator(mode="after")
    def _one_source(self) -> SpeakRequest:
        """Exactly one of ``items`` or ``lesson_id`` must be given."""
        if bool(self.items) == bool(self.lesson_id):
            raise ValueError("give either items or lesson_id")
        return self


class SpeakResponse(StrictModel):
    """Synthesized speech for rendered, filtered template text."""

    kind: Literal["speech"] = "speech"
    audio_base64: str = Field(description="Base64 audio.")
    audio_format: str = Field(description="Audio format, e.g. 'wav'.")
    provider: str = Field(description="Which speech provider produced it.")
    meta: ResponseMeta = Field(description="Metadata.")


class CardsRequest(StrictModel):
    """Body of ``POST /v1/cards``."""

    locale: str = Field(pattern=LOCALE_PATTERN, description="Language for the cards.")
    event: DecisionEvent = Field(description="The decision event.")
    profile: UserProfile = Field(default_factory=UserProfile, description="Device snapshot.")


class CardsResponse(StrictModel):
    """Cards for an event and profile."""

    kind: Literal["cards"] = "cards"
    cards: list[ExplanationCard] = Field(max_length=3, description="At most 3 cards.")
    meta: ResponseMeta = Field(description="Metadata.")


class PaymentMethod(StrEnum):
    """How money left the user's account."""

    UPI = "upi"
    BANK_TRANSFER = "bank_transfer"
    CARD = "card"
    CASH_OR_OTHER = "cash_or_other"
    NONE = "none"


class RecoveryAnswers(StrictModel):
    """Answers to the recovery questions. No account numbers, OTPs or PINs, ever."""

    paid_money: bool = Field(description="Did money leave your account?")
    payment_method: PaymentMethod = Field(
        default=PaymentMethod.NONE, description="How it was paid."
    )
    installed_app: bool = Field(
        default=False, description="Did you install an app they sent, or share your screen?"
    )
    registered_broker_involved: bool = Field(
        default=False, description="Is this about your own registered broker or DP account?"
    )
    unauthorized_trade: bool = Field(
        default=False, description="Did a trade happen in your account that you did not place?"
    )
    cannot_withdraw: bool = Field(
        default=False, description="Is a 'platform' refusing to let you withdraw?"
    )


class RecoverRequest(StrictModel):
    """Body of ``POST /v1/recover``."""

    locale: str = Field(pattern=LOCALE_PATTERN, description="Language for the guide.")
    answers: RecoveryAnswers = Field(description="Scenario answers.")


class JournalReviewRequest(StrictModel):
    """Body of ``POST /v1/journal/review``. The journal is not stored."""

    locale: str = Field(pattern=LOCALE_PATTERN, description="Language for highlights.")
    entries: list[JournalEntry] = Field(max_length=1000, description="Device journal entries.")
    as_of: dt.date | None = Field(default=None, description="Review date (defaults to today).")


class AmountBand(StrictModel):
    """An order value range. The broker sends a band, not the exact value."""

    min_inr: int = Field(ge=0, description="Lower bound in rupees.")
    max_inr: int = Field(ge=1, description="Upper bound in rupees (used for rule checks).")

    @model_validator(mode="after")
    def _ordered(self) -> AmountBand:
        if self.min_inr > self.max_inr:
            raise ValueError("min_inr must not exceed max_inr")
        return self


class OrderIntentRequest(StrictModel):
    """Body of ``POST /v1/order-intent`` (broker embedding). No instrument, no user ID."""

    product_class: ProductClass = Field(description="Product class of the order.")
    amount_band: AmountBand = Field(description="Order value band.")
    borrowed_funds: bool = Field(default=False, description="User flagged borrowed money.")
    leveraged: bool = Field(default=False, description="Order uses leverage / margin.")
    plan_matched: bool | None = Field(
        default=None,
        description="The order follows a plan the user logged in their Ruko app; None = unknown.",
    )
    profile: UserProfile = Field(
        default_factory=UserProfile, description="Snapshot the user chose to share."
    )


class OrderIntentResponse(StrictModel):
    """Level and reason codes only. No text, no advice."""

    kind: Literal["order_intent"] = "order_intent"
    level: InterventionLevel = Field(description="Intervention level.")
    reason_codes: list[ReasonCode] = Field(description="Reasons, most severe first.")
    override_allowed: Literal[True] = True
    policy_version: str = Field(description="Policy version used.")
