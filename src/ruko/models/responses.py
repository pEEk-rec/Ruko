"""API response contracts: pause, refusal, clarify, cards."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from ruko.models.common import (
    LOCALE_PATTERN,
    Action,
    CalculationField,
    CalculatorTool,
    Certainty,
    DecisionStage,
    InterventionLevel,
    ProductClass,
    ReasonCode,
    RefusalClass,
    Severity,
    SourceRef,
    SourceType,
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
    role: str | None = Field(
        default=None,
        description="What the signal is doing: pressure, claims, source, or you (about the user).",
    )
    role_label: str | None = Field(
        default=None, description="Rendered heading for the role, in the user's language."
    )
    certainty: Certainty = Field(description="possible / likely / unclear.")
    severity: Severity | None = Field(default=None, description="Severity tier of the code.")
    text: str = Field(description="Rendered, filtered line: certainty label + explanation.")
    certainty_label: str | None = Field(
        default=None, description="Rendered certainty word alone (for a badge), in the locale."
    )
    reason_text: str | None = Field(
        default=None, description="Rendered explanation without the certainty label."
    )
    quote: str | None = Field(
        default=None,
        max_length=160,
        description=(
            "A short excerpt of the user's own (redacted) message that this signal rests on. "
            "Not Ruko's wording: never validated as Ruko text, never logged, never spoken."
        ),
    )


class EventSummary(StrictModel):
    """What the decision was about, without any message text (for the device journal)."""

    stage: DecisionStage = Field(description="Decision stage.")
    action: Action = Field(description="What the user means to do.")
    product_class: ProductClass = Field(description="Broad product class.")
    source_type: SourceType = Field(description="Where the content came from.")


class TermHit(StrictModel):
    """A glossary term found in a Ruko text, so the app can make the word tappable.

    ``match`` is the exact words as they appear in the text; ``brief`` is a short, curated
    explanation shown in a small pop-up. Never written by the LLM.
    """

    id: str = Field(description="Glossary entry ID.")
    match: str = Field(description="The words in the text that name the term.")
    title: str = Field(description="Rendered term name.")
    brief: str = Field(description="Rendered one- or two-line explanation for the pop-up.")


class LessonTopic(StrictModel):
    """A lesson as listed or suggested: enough to choose it, not the lesson itself."""

    id: str = Field(description="Lesson ID.")
    title: str = Field(description="Rendered title.")
    summary: str = Field(description="Rendered one-line summary.")
    read_seconds: int = Field(ge=1, description="Estimated reading time.")
    topic: str = Field(description="Topic ID the lesson is listed under.")
    seen: bool = Field(default=False, description="The device says it was read.")
    safety_critical: bool = Field(default=False, description="About spotting or avoiding fraud.")


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


class Lesson(StrictModel):
    """A short, curated micro-lesson chosen for this decision. Never a recommendation.

    Text comes from ``lesson.<id>.*`` templates (never from the LLM); numbers are the
    user's own. ``speak`` reads exactly this lesson aloud via ``/v1/speak``.
    """

    id: str = Field(description="Lesson ID from data/learn/lessons.yaml.")
    title: str = Field(description="Rendered title.")
    body: str = Field(description="Rendered body (about 60 to 120 words).")
    read_seconds: int = Field(ge=1, description="Estimated reading time.")
    safety_critical: bool = Field(default=False, description="Shown even if seen before.")
    related_tool: CalculatorTool | None = Field(
        default=None, description="A calculator this lesson points to, if any."
    )
    as_of: str | None = Field(default=None, description="Date the lesson was checked against.")
    sources: list[SourceRef] = Field(default_factory=list, description="Citations.")
    verified_by_human: bool = Field(
        default=False, description="Lesson text and all its facts human-verified."
    )
    speak: list[TemplateRef] = Field(
        default_factory=list, description="What /v1/speak should read for this lesson."
    )
    summary: str | None = Field(default=None, description="Rendered one-line summary.")
    own_guidance: bool = Field(
        default=False, description="General habit advice from Ruko, not from an official source."
    )


class RecoveryEntry(StrictModel):
    """Pointer to the recovery path ('I already paid / something went wrong')."""

    text: str = Field(description="Rendered prompt, e.g. 'Already paid? Get help now'.")
    endpoint: Literal["/v1/recover"] = "/v1/recover"


class ClarifyOption(StrictModel):
    """One answer choice for a clarifying question."""

    value: str = Field(description="Machine value sent back in the next request.")
    label: str = Field(description="Rendered label.")


class ClarifyQuestion(StrictModel):
    """A question for a field the engine needs and that Ruko must not guess."""

    field: EventField | CalculationField = Field(
        description="Which DecisionEvent field (or calculator input) this answers."
    )
    text: str = Field(description="Rendered question.")
    options: list[ClarifyOption] = Field(
        default_factory=list, description="Choices; empty means free numeric input."
    )
    hints: list[ClarifyOption] = Field(
        default_factory=list,
        description=(
            "Values the user's own message mentions (for example an amount), offered as "
            "one-tap confirmations. Never applied without the user tapping one."
        ),
    )
    suggested: str | None = Field(
        default=None,
        description="An option value that matches what the message describes, for a tag.",
    )
    suggested_tag: str | None = Field(
        default=None, description="Rendered tag shown next to the suggested option."
    )


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
    lessons: list[Lesson] = Field(
        default_factory=list,
        max_length=2,
        description="At most 2 lessons; cards + lessons together at most 3.",
    )
    recovery_entry: RecoveryEntry | None = Field(default=None, description="Recovery pointer.")
    learn_next: LessonTopic | None = Field(
        default=None,
        description="One lesson worth reading next, when this result carries none (quiet pauses).",
    )
    terms: list[TermHit] = Field(
        default_factory=list,
        description="Glossary words used anywhere in this response, tappable in the app.",
    )
    refine: list[ClarifyQuestion] = Field(
        default_factory=list,
        description=(
            "Questions that would personalise this pause (amount, funding source), present "
            "when a high-severity message was shown before asking. Answering re-runs the check."
        ),
    )
    override_label: str = Field(description="Rendered label for 'continue anyway'.")
    speak: list[TemplateRef] = Field(
        default_factory=list, description="What /v1/speak should read aloud."
    )
    decision: InterventionDecision = Field(description="The engine's structured decision.")
    event: EventSummary | None = Field(
        default=None, description="What the decision was about (no message text)."
    )
    meta: ResponseMeta = Field(description="Metadata.")


class RefusalResponse(StrictModel):
    """A fixed, pre-written response for inputs Ruko will not process."""

    kind: Literal["refusal"] = "refusal"
    refusal_class: RefusalClass = Field(description="Why the input was refused.")
    message: str = Field(description="Rendered refusal message.")
    alternative: str = Field(description="Rendered offer of what Ruko can do instead.")
    terms: list[TermHit] = Field(
        default_factory=list,
        description="Glossary words used anywhere in this response, tappable in the app.",
    )
    speak: list[TemplateRef] = Field(
        default_factory=list, description="What /v1/speak should read aloud."
    )
    meta: ResponseMeta = Field(description="Metadata.")


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
    lessons: list[Lesson] = Field(
        default_factory=list,
        max_length=2,
        description="At most 2 lessons; cards + lessons together at most 3.",
    )
    learn_next: LessonTopic | None = Field(
        default=None, description="One lesson worth reading next, if the report carries none."
    )
    terms: list[TermHit] = Field(
        default_factory=list,
        description="Glossary words used anywhere in this response, tappable in the app.",
    )
    recovery_entry: RecoveryEntry | None = Field(default=None, description="Recovery pointer.")
    speak: list[TemplateRef] = Field(
        default_factory=list, description="What /v1/speak should read aloud."
    )
    meta: ResponseMeta = Field(description="Metadata.")


class GlossaryChip(StrictModel):
    """Another term Ruko can explain, offered as a one-tap follow-up."""

    id: str = Field(description="Glossary entry ID.")
    title: str = Field(description="Rendered title (also the question to send to ask about it).")


class GlossaryResponse(StrictModel):
    """The learn path: a curated, plain-language explanation (or an official pointer)."""

    kind: Literal["glossary"] = "glossary"
    found: bool = Field(description="True if the term is in Ruko's glossary.")
    term: str | None = Field(default=None, description="Glossary entry ID.")
    title: str | None = Field(default=None, description="Rendered title.")
    body: str = Field(description="Rendered explanation, or the 'not in the glossary' line.")
    sources: list[SourceRef] = Field(default_factory=list, description="Citations / pointers.")
    related: list[GlossaryChip] = Field(
        default_factory=list, description="Other terms Ruko can explain."
    )
    terms: list[TermHit] = Field(
        default_factory=list,
        description="Glossary words used anywhere in this response, tappable in the app.",
    )
    learn_next: LessonTopic | None = Field(
        default=None, description="A lesson that goes deeper on this term, if there is one."
    )
    speak: list[TemplateRef] = Field(
        default_factory=list, description="What /v1/speak should read aloud."
    )
    meta: ResponseMeta = Field(description="Metadata.")


class TopicGroup(StrictModel):
    """A heading in the Learn list with its lessons."""

    id: str = Field(description="Topic ID.")
    title: str = Field(description="Rendered heading.")
    lessons: list[LessonTopic] = Field(description="Lessons under this heading, in reading order.")


class GlossaryEntry(StrictModel):
    """One term in the Learn list row of words people hear."""

    id: str = Field(description="Glossary entry ID.")
    title: str = Field(description="Rendered term name (also the question that asks about it).")
    brief: str = Field(description="Rendered short explanation for the pop-up.")


class LearnHubResponse(StrictModel):
    """The Learn list: always available, no trigger needed."""

    kind: Literal["learn_hub"] = "learn_hub"
    featured: LessonTopic | None = Field(
        default=None, description="The lesson to read next for this person (None if all read)."
    )
    read_count: int = Field(ge=0, description="Lessons the device reports as read.")
    total: int = Field(ge=0, description="Lessons in the list (0 while none is human-checked).")
    topics: list[TopicGroup] = Field(description="Every lesson, grouped by topic.")
    words: list[GlossaryEntry] = Field(description="Glossary terms with a short explanation.")
    meta: ResponseMeta = Field(description="Metadata.")


class LessonResponse(StrictModel):
    """One whole lesson, opened from the Learn list or from a suggestion."""

    kind: Literal["lesson"] = "lesson"
    lesson: Lesson = Field(description="The lesson, with tappable terms.")
    next: LessonTopic | None = Field(default=None, description="The lesson to read after this.")
    terms: list[TermHit] = Field(
        default_factory=list,
        description="Glossary words used anywhere in this response, tappable in the app.",
    )
    meta: ResponseMeta = Field(description="Metadata.")
