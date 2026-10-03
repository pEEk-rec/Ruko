"""API response contracts: pause, refusal, clarify, cards."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from ruko.models.common import (
    LOCALE_PATTERN,
    Certainty,
    DecisionStage,
    InterventionLevel,
    ReasonCode,
    RefusalClass,
    Severity,
    SourceRef,
    StrictModel,
)
from ruko.models.decision import InterventionDecision
from ruko.models.event import DecisionEvent, EventField


class TemplateRef(StrictModel):
    """A template key plus slot values.

    ``/v1/speak`` re-renders and re-filters these, so text-to-speech can only ever
    read Ruko's own templates.
    """

    key: str = Field(min_length=1, max_length=120, description="Template key.")
    slots: dict[str, str] = Field(
        default_factory=dict, description="Slot values (short strings, e.g. rupee amounts)."
    )


class TraceStep(StrictModel):
    """One workflow step, for transparency. Contains names and timings, never content."""

    step: str = Field(description="Step or tool name.")
    status: Literal["ok", "skipped", "failed", "fallback"] = Field(description="Outcome.")
    duration_ms: float = Field(ge=0, description="Wall time in milliseconds.")
    reason_codes: list[ReasonCode] = Field(
        default_factory=list, description="Codes produced by this step, if any."
    )


class ResponseMeta(StrictModel):
    """Metadata for honesty and debugging; safe to show and to log."""

    request_id: str = Field(description="Request ID (also in the x-request-id header).")
    locale: str = Field(pattern=LOCALE_PATTERN, description="Language of the rendered text.")
    policy_version: str | None = Field(default=None, description="Intervention policy version.")
    prompt_version: str | None = Field(default=None, description="LLM prompt version, if used.")
    extraction_mode: Literal["llm", "lexicon_only", "not_run"] = Field(
        default="not_run", description="Whether the LLM was used or the lexicon fallback."
    )
    stage: DecisionStage | None = Field(default=None, description="Decision stage of the input.")
    stage_source: Literal["lexicon", "llm", "user", "default"] | None = Field(
        default=None, description="Who decided the stage."
    )
    unverified_fact_ids: list[str] = Field(
        default_factory=list, description="Displayed facts not yet verified by a human."
    )
    draft_template_count: int = Field(
        default=0, ge=0, description="Rendered templates still in draft status."
    )
    missing_template_keys: list[str] = Field(
        default_factory=list, description="Keys that fell back to English."
    )
    blocked_output_count: int = Field(
        default=0, ge=0, description="Strings replaced by the output filter."
    )
    trace: list[TraceStep] = Field(default_factory=list, description="Steps that ran.")


class SignalView(StrictModel):
    """A signal as shown to the user: always with its certainty."""

    code: ReasonCode = Field(description="Reason code.")
    certainty: Certainty = Field(description="possible / likely / unclear.")
    severity: Severity | None = Field(default=None, description="Severity tier of the code.")
    text: str = Field(description="Rendered, filtered explanation.")


class ExplanationCard(StrictModel):
    """A short just-in-time explanation. Never a recommendation."""

    id: str = Field(description="Card ID from data/cards/catalog.yaml.")
    title: str = Field(description="Rendered title.")
    body: str = Field(description="Rendered body, in the user's rupees and language.")
    safety_critical: bool = Field(
        default=False, description="Shown even if seen before (scam-related)."
    )
    as_of: str | None = Field(default=None, description="Date the card's facts are valid as of.")
    sources: list[SourceRef] = Field(default_factory=list, description="Citations.")
    verified_by_human: bool = Field(default=False, description="All facts human-verified.")


class RecoveryEntry(StrictModel):
    """Pointer to the recovery path ('I already paid / something went wrong')."""

    text: str = Field(description="Rendered prompt, e.g. 'Already paid? Get help now'.")
    endpoint: Literal["/v1/recover"] = "/v1/recover"


class PauseResponse(StrictModel):
    """The pause screen: your numbers, your rules, signals, one question, few cards."""

    kind: Literal["pause"] = "pause"
    level: InterventionLevel = Field(description="Intervention level.")
    headline: str = Field(description="One rendered line for the top of the screen.")
    numbers_text: list[str] = Field(default_factory=list, description="Your numbers, rendered.")
    rules_text: list[str] = Field(default_factory=list, description="Your rules, rendered.")
    signals: list[SignalView] = Field(default_factory=list, description="Signals with certainty.")
    question: str | None = Field(default=None, description="One reflection question.")
    cards: list[ExplanationCard] = Field(
        default_factory=list, max_length=3, description="At most 3 cards."
    )
    recovery_entry: RecoveryEntry | None = Field(default=None, description="Recovery pointer.")
    override_label: str = Field(description="Rendered label for 'continue anyway'.")
    speak: list[TemplateRef] = Field(
        default_factory=list, description="What /v1/speak should read aloud."
    )
    decision: InterventionDecision = Field(description="The engine's structured decision.")
    meta: ResponseMeta = Field(description="Metadata.")


class RefusalResponse(StrictModel):
    """A fixed, pre-written response for inputs Ruko will not process."""

    kind: Literal["refusal"] = "refusal"
    refusal_class: RefusalClass = Field(description="Why the input was refused.")
    message: str = Field(description="Rendered refusal message.")
    alternative: str = Field(description="Rendered offer of what Ruko can do instead.")
    speak: list[TemplateRef] = Field(
        default_factory=list, description="What /v1/speak should read aloud."
    )
    meta: ResponseMeta = Field(description="Metadata.")


class ClarifyOption(StrictModel):
    """One answer choice for a clarifying question."""

    value: str = Field(description="Machine value sent back in the next request.")
    label: str = Field(description="Rendered label.")


class ClarifyQuestion(StrictModel):
    """A question for a field the engine needs and that Ruko must not guess."""

    field: EventField = Field(description="Which DecisionEvent field this answers.")
    text: str = Field(description="Rendered question.")
    options: list[ClarifyOption] = Field(
        default_factory=list, description="Choices; empty means free numeric input."
    )


class ClarifyResponse(StrictModel):
    """Returned instead of a decision when required fields are missing."""

    kind: Literal["clarify"] = "clarify"
    questions: list[ClarifyQuestion] = Field(min_length=1, description="Questions to ask.")
    event: DecisionEvent = Field(description="What was understood so far.")
    speak: list[TemplateRef] = Field(
        default_factory=list, description="What /v1/speak should read aloud."
    )
    meta: ResponseMeta = Field(description="Metadata.")


class ContentReportResponse(StrictModel):
    """The evaluate_content path: what the message itself shows. No verdict, no engine."""

    kind: Literal["content_report"] = "content_report"
    headline: str = Field(description="Rendered headline (includes 'Ruko can't vouch').")
    signals: list[SignalView] = Field(
        default_factory=list, description="Content signals with severity and certainty."
    )
    note: str | None = Field(default=None, description="Rendered line when nothing was found.")
    cards: list[ExplanationCard] = Field(
        default_factory=list, max_length=3, description="Safety-critical cards for the signals."
    )
    recovery_entry: RecoveryEntry | None = Field(default=None, description="Recovery pointer.")
    speak: list[TemplateRef] = Field(
        default_factory=list, description="What /v1/speak should read aloud."
    )
    meta: ResponseMeta = Field(description="Metadata.")


class GlossaryResponse(StrictModel):
    """The learn path: a curated, plain-language explanation (or an official pointer)."""

    kind: Literal["glossary"] = "glossary"
    found: bool = Field(description="True if the term is in Ruko's glossary.")
    term: str | None = Field(default=None, description="Glossary entry ID.")
    title: str | None = Field(default=None, description="Rendered title.")
    body: str = Field(description="Rendered explanation, or the 'not in the glossary' line.")
    sources: list[SourceRef] = Field(default_factory=list, description="Citations / pointers.")
    speak: list[TemplateRef] = Field(
        default_factory=list, description="What /v1/speak should read aloud."
    )
    meta: ResponseMeta = Field(description="Metadata.")
