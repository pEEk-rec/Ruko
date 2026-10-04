"""Deterministic clarifying questions for fields the engine needs and Ruko must not guess.

Configured in ``data/policy/clarify.yaml``. For a financial decision, Ruko asks (in order)
for the amount, the funding source and the product class when they are still unknown.

- An answer of ``unknown`` ("prefer not to say" / "not sure") counts as answered.
- Fields the user skipped are not asked again, but stay listed in ``missing_fields``.
- If the message has a high-severity fraud pattern, no questions are asked first: the
  warning is shown at once.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache

from ruko.data_files import load_yaml
from ruko.engine.policy import InterventionPolicy, get_intervention_policy
from ruko.language.numbers import rupees
from ruko.language.templates import Renderer
from ruko.models.common import (
    Dimension,
    FundingSource,
    ProductClass,
    ReasonCode,
    Severity,
    dimension_of,
)
from ruko.models.event import DecisionEvent, EventField
from ruko.models.requests import DecisionAnswers
from ruko.models.responses import ClarifyOption, ClarifyQuestion

AMOUNT_HINT_KEY = "clarify.amount_inr.hint"
SUGGESTED_TAG_KEY = "clarify.suggested_tag"


@dataclass(frozen=True)
class ClarifyField:
    """One askable field: its question template and answer choices."""

    field: EventField
    question_key: str
    options: tuple[str, ...]

    def option_key(self, value: str) -> str:
        """Return the template key for one answer choice."""
        return f"clarify.{self.field}.option.{value}"


@dataclass(frozen=True)
class ClarifyPolicy:
    """The clarify configuration."""

    version: str
    max_questions: int
    skip_when_content_severity: Severity
    fields: tuple[ClarifyField, ...]
    amount_hints: int = 2
    suggest: dict[str, dict[str, frozenset[ReasonCode]]] = field(default_factory=dict)

    def template_keys(self) -> set[str]:
        """Return every template key the questions use (for the template linter)."""
        keys: set[str] = {AMOUNT_HINT_KEY, SUGGESTED_TAG_KEY}
        for item in self.fields:
            keys.add(item.question_key)
            keys |= {item.option_key(v) for v in item.options}
        return keys


@lru_cache(maxsize=1)
def get_clarify_policy() -> ClarifyPolicy:
    """Load ``data/policy/clarify.yaml`` (cached)."""
    raw = load_yaml("policy", "clarify.yaml")
    return ClarifyPolicy(
        version=str(raw["version"]),
        max_questions=int(raw["max_questions"]),
        skip_when_content_severity=Severity(raw["skip_when_content_severity"]),
        fields=tuple(
            ClarifyField(f["field"], f["question_key"], tuple(f["options"])) for f in raw["fields"]
        ),
        amount_hints=int(raw.get("amount_hints", 2)),
        suggest={
            name: {
                value: frozenset(ReasonCode(code) for code in codes)
                for value, codes in choices.items()
            }
            for name, choices in (raw.get("suggest") or {}).items()
        },
    )


def _is_answered(name: EventField, event: DecisionEvent, answers: DecisionAnswers) -> bool:
    if name == "amount_inr":
        return event.amount_inr is not None
    if name == "funding_source":
        return event.funding_source != FundingSource.UNKNOWN or answers.funding_source is not None
    if name == "product_class":
        return event.product_class != ProductClass.UNKNOWN or answers.product_class is not None
    return True


def missing_fields(
    event: DecisionEvent, answers: DecisionAnswers, policy: ClarifyPolicy | None = None
) -> list[EventField]:
    """Return the needed fields that are still unknown (only for a financial decision)."""
    policy = policy or get_clarify_policy()
    if not event.is_financial_decision:
        return []
    return [f.field for f in policy.fields if not _is_answered(f.field, event, answers)]


def fields_to_ask(
    event: DecisionEvent,
    answers: DecisionAnswers,
    policy: ClarifyPolicy | None = None,
    intervention: InterventionPolicy | None = None,
) -> list[ClarifyField]:
    """Return the questions to ask now, in order (empty means: go ahead and decide)."""
    policy = policy or get_clarify_policy()
    intervention = intervention or get_intervention_policy()
    threshold = policy.skip_when_content_severity.rank
    if any(
        dimension_of(code) == Dimension.CONTENT and intervention.severity(code).rank >= threshold
        for code in event.signal_codes()
    ):
        return []
    missing = set(missing_fields(event, answers, policy)) - set(answers.skipped_fields)
    return [f for f in policy.fields if f.field in missing][: policy.max_questions]


def refine_fields(
    event: DecisionEvent, answers: DecisionAnswers, policy: ClarifyPolicy | None = None
) -> list[ClarifyField]:
    """Return the unanswered, unskipped fields even when a warning came first.

    When a high-severity message is shown at once, the questions are not asked up front; the
    pause carries them instead so the person can add their own numbers and see what it means.
    """
    policy = policy or get_clarify_policy()
    missing = set(missing_fields(event, answers, policy)) - set(answers.skipped_fields)
    return [f for f in policy.fields if f.field in missing][: policy.max_questions]


def with_missing_fields(event: DecisionEvent, answers: DecisionAnswers) -> DecisionEvent:
    """Return the event with ``missing_fields`` filled in."""
    return event.model_copy(update={"missing_fields": missing_fields(event, answers)})


_COUNTS = re.compile(
    r"\d[\d,.]*\s*(?:k\s*)?(?:members?|followers?|subscribers?|views?|likes?|people|users?"
    r"|traders?|students?|joined|सदस्य|फ़ॉलोअर्स|ಸದಸ್ಯರು|ಸದಸ್ಯ)",
    re.IGNORECASE,
)
"""Numbers that count people or views ("48,213 members"), never an amount to offer."""


def _amount_hints(redacted: str, renderer: Renderer, limit: int) -> list[ClarifyOption]:
    """Amounts the message itself mentions, as one-tap confirmations (most mentioned first)."""
    from ruko.tools.params import read_numbers

    mentioned = read_numbers(_COUNTS.sub(" ", redacted)).amounts
    unique = sorted(
        set(mentioned), key=lambda value: (-mentioned.count(value), mentioned.index(value))
    )
    return [
        ClarifyOption(
            value=str(amount), label=renderer.text(AMOUNT_HINT_KEY, amount=rupees(amount))
        )
        for amount in unique[:limit]
    ]


def render_questions(
    fields: list[ClarifyField],
    renderer: Renderer,
    redacted: str = "",
    event: DecisionEvent | None = None,
    policy: ClarifyPolicy | None = None,
) -> list[ClarifyQuestion]:
    """Render questions and answer labels through the template renderer (output-filtered).

    Args:
        fields: The questions to ask.
        renderer: Renderer for the user's locale.
        redacted: The redacted message, searched in memory for amounts it mentions.
        event: What was understood, used to tag the answer that matches the message.
        policy: Optional policy override.

    Returns:
        Questions with their options, plus amount hints and a suggested-option tag where the
        message supports one.
    """
    policy = policy or get_clarify_policy()
    codes = set(event.signal_codes()) if event is not None else set()
    questions: list[ClarifyQuestion] = []
    for item in fields:
        hints = (
            _amount_hints(redacted, renderer, policy.amount_hints)
            if item.field == "amount_inr" and redacted
            else []
        )
        suggested = next(
            (
                value
                for value, triggers in policy.suggest.get(item.field, {}).items()
                if value in item.options and triggers & codes
            ),
            None,
        )
        questions.append(
            ClarifyQuestion(
                field=item.field,
                text=renderer.text(item.question_key),
                options=[
                    ClarifyOption(value=v, label=renderer.text(item.option_key(v)))
                    for v in item.options
                ],
                hints=hints,
                suggested=suggested,
                suggested_tag=renderer.text(SUGGESTED_TAG_KEY) if suggested else None,
            )
        )
    return questions
