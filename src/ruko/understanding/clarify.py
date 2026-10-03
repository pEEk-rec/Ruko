"""Deterministic clarifying questions for fields the engine needs and Ruko must not guess.

Configured in ``data/policy/clarify.yaml``. For a financial decision, Ruko asks (in order)
for the amount, the funding source and the product class when they are still unknown.

- An answer of ``unknown`` ("prefer not to say" / "not sure") counts as answered.
- Fields the user skipped are not asked again, but stay listed in ``missing_fields``.
- If the message has a high-severity fraud pattern, no questions are asked first: the
  warning is shown at once.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from ruko.data_files import load_yaml
from ruko.engine.policy import InterventionPolicy, get_intervention_policy
from ruko.language.templates import Renderer
from ruko.models.common import Dimension, FundingSource, ProductClass, Severity, dimension_of
from ruko.models.event import DecisionEvent, EventField
from ruko.models.requests import DecisionAnswers
from ruko.models.responses import ClarifyOption, ClarifyQuestion


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

    def template_keys(self) -> set[str]:
        """Return every template key the questions use (for the template linter)."""
        keys: set[str] = set()
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


def with_missing_fields(event: DecisionEvent, answers: DecisionAnswers) -> DecisionEvent:
    """Return the event with ``missing_fields`` filled in."""
    return event.model_copy(update={"missing_fields": missing_fields(event, answers)})


def render_questions(fields: list[ClarifyField], renderer: Renderer) -> list[ClarifyQuestion]:
    """Render questions and answer labels through the template renderer (output-filtered)."""
    return [
        ClarifyQuestion(
            field=item.field,
            text=renderer.text(item.question_key),
            options=[
                ClarifyOption(value=v, label=renderer.text(item.option_key(v)))
                for v in item.options
            ],
        )
        for item in fields
    ]
