"""Assemble the pause screen from the engine's decision (``data/policy/pause.yaml``).

What is shown depends only on the level: L0 is a quiet headline; L1 adds the top reason
and one question; L2/L3 show the user's numbers, their own rules, every reason with its
certainty, one question and up to 3 cards. Every string goes through the ``Renderer``
(output filter), and every string has a matching ``TemplateRef`` for ``/v1/speak``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Literal

from ruko.data_files import load_yaml
from ruko.engine.base_rates import format_percent
from ruko.engine.policy import get_intervention_policy
from ruko.language.numbers import rupees
from ruko.language.templates import Renderer
from ruko.learn.select import explain_decision
from ruko.models.common import InterventionLevel, ReasonCode
from ruko.models.decision import InterventionDecision, NumberRange
from ruko.models.event import DecisionEvent
from ruko.models.profile import UserProfile
from ruko.models.responses import (
    EventSummary,
    ExplanationCard,
    PauseResponse,
    RecoveryEntry,
    ResponseMeta,
    SignalView,
    TemplateRef,
)
from ruko.orchestrator.signal_view import render_signal

SignalsShown = Literal["none", "top", "all"]
NUMBER_KEYS = ("pause.numbers.amount",) + tuple(
    f"pause.numbers.{name}{suffix}"
    for name in ("months", "share", "buffer")
    for suffix in ("", "_exact")
)
FIXED_KEYS = frozenset(
    {
        *NUMBER_KEYS,
        *(f"pause.headline.{level.value}" for level in InterventionLevel),
        "pause.headline.urgent.L2",
        "pause.headline.urgent.L3",
        "pause.rule.max_share",
        "pause.rule.max_amount",
        "pause.rule.no_borrowed",
        "pause.cooling_off.own",
        "pause.cooling_off.suggested",
        "pause.override",
        "pause.recovery_entry",
        "verdict.cannot_vouch",
        "certainty.likely",
        "certainty.possible",
        "certainty.unclear",
        *(f"reason.{code.value.lower()}" for code in ReasonCode),
    }
)
"""Template keys the pause screen can render (the questions come from the policy file)."""


@dataclass(frozen=True)
class LevelShow:
    """What one level shows."""

    numbers: bool
    rules: bool
    signals: SignalsShown
    question: bool


@dataclass(frozen=True)
class PausePolicy:
    """The pause policy file."""

    show: dict[InterventionLevel, LevelShow]
    question_by_category: dict[str, str]
    default_question: str


@lru_cache(maxsize=1)
def get_pause_policy() -> PausePolicy:
    """Load ``data/policy/pause.yaml`` (cached)."""
    raw = load_yaml("policy", "pause.yaml")
    return PausePolicy(
        show={InterventionLevel(k): LevelShow(**v) for k, v in raw["show"].items()},
        question_by_category=dict(raw["question_by_category"]),
        default_question=raw["default_question"],
    )


@dataclass
class _Lines:
    """Rendered lines plus their template references, kept in step."""

    renderer: Renderer
    texts: list[str] = field(default_factory=list)
    refs: list[TemplateRef] = field(default_factory=list)

    def add(self, key: str, **slots: str) -> str:
        text = self.renderer.text(key, **slots)
        self.texts.append(text)
        self.refs.append(TemplateRef(key=key, slots=slots))
        return text


def _fmt(value: float) -> str:
    return format_percent(round(value, 1))


def _range_line(lines: _Lines, name: str, value: NumberRange | None) -> None:
    if value is None:
        return
    if value.low == value.high:
        lines.add(f"pause.numbers.{name}_exact", value=_fmt(value.typical))
    else:
        lines.add(
            f"pause.numbers.{name}",
            typical=_fmt(value.typical),
            low=_fmt(value.low),
            high=_fmt(value.high),
        )


def _numbers(decision: InterventionDecision, renderer: Renderer) -> _Lines:
    lines = _Lines(renderer)
    numbers = decision.exposure
    if numbers.amount_inr is None:
        return lines
    lines.add("pause.numbers.amount", amount=rupees(numbers.amount_inr))
    _range_line(lines, "months", numbers.months_of_expenses)
    _range_line(lines, "share", numbers.share_of_savings_pct)
    _range_line(lines, "buffer", numbers.remaining_buffer_months)
    return lines


def _rules(decision: InterventionDecision, profile: UserProfile, renderer: Renderer) -> _Lines:
    lines = _Lines(renderer)
    codes = set(decision.reason_codes)
    rules = profile.rules
    if ReasonCode.RULE_MAX_SHARE_EXCEEDED in codes and rules.max_share_of_savings_pct:
        lines.add("pause.rule.max_share", pct=str(rules.max_share_of_savings_pct))
    if ReasonCode.RULE_MAX_AMOUNT_EXCEEDED in codes and rules.max_amount_inr:
        lines.add("pause.rule.max_amount", amount=rupees(rules.max_amount_inr))
    if ReasonCode.BORROWED_FUNDS in codes and rules.no_borrowed_money:
        lines.add("pause.rule.no_borrowed")
    if decision.cooling_off_minutes:
        own = rules.cooling_off_minutes == decision.cooling_off_minutes
        key = "pause.cooling_off.own" if own else "pause.cooling_off.suggested"
        lines.add(key, minutes=str(decision.cooling_off_minutes))
    return lines


def _signals(
    decision: InterventionDecision, shown: SignalsShown, renderer: Renderer
) -> tuple[list[SignalView], list[TemplateRef]]:
    reasons = {"none": [], "top": decision.reasons[:1], "all": decision.reasons}[shown]
    views: list[SignalView] = []
    refs: list[TemplateRef] = []
    for reason in reasons:
        view, view_refs = render_signal(reason, renderer)
        views.append(view)
        refs += view_refs
    return views, refs


def question_key(decision: InterventionDecision, policy: PausePolicy | None = None) -> str:
    """Return the reflection-question template for the most severe reason's category."""
    policy = policy or get_pause_policy()
    if not decision.reasons:
        return policy.default_question
    category = get_intervention_policy().codes[decision.reasons[0].code].category
    return policy.question_by_category.get(category, policy.default_question)


@dataclass
class PauseContent:
    """Everything on the pause screen except the metadata."""

    fields: dict[str, object]
    speak: list[TemplateRef]
    unverified_fact_ids: list[str]

    def to_response(self, meta: ResponseMeta) -> PauseResponse:
        """Attach metadata and build the response model."""
        return PauseResponse.model_validate({**self.fields, "speak": self.speak, "meta": meta})


def build_pause(
    event: DecisionEvent,
    decision: InterventionDecision,
    profile: UserProfile,
    renderer: Renderer,
    *,
    verdict_requested: bool = False,
    urgent: bool = False,
    show_unverified: bool = True,
) -> PauseContent:
    """Render the pause screen for one decision.

    Args:
        event: The decision event.
        decision: The engine's decision.
        profile: Device snapshot (rules, seen cards).
        renderer: Renderer for the user's locale.
        verdict_requested: The user asked "is this a scam/safe?": add the fixed
            "Ruko can't vouch" line instead of any verdict.
        urgent: The user is about to act right now: L2/L3 use the urgent headline.
        show_unverified: False in production: cards stating unverified facts are left out.

    Returns:
        The rendered content, speech references and unverified fact IDs.
    """
    policy = get_pause_policy()
    show = policy.show[decision.level]
    head = _Lines(renderer)
    if verdict_requested:
        head.add("verdict.cannot_vouch")
    level = decision.level.value
    urgent_level = urgent and decision.level.rank >= InterventionLevel.L2.rank
    head.add(f"pause.headline.urgent.{level}" if urgent_level else f"pause.headline.{level}")
    numbers = _numbers(decision, renderer) if show.numbers else _Lines(renderer)
    rules = _rules(decision, profile, renderer) if show.rules else _Lines(renderer)
    signals, signal_refs = _signals(decision, show.signals, renderer)
    question = _Lines(renderer)
    if show.question:
        question.add(question_key(decision, policy))
    explained = explain_decision(
        event, decision, profile, renderer, show_unverified=show_unverified
    )
    cards: list[ExplanationCard] = explained.cards.cards
    recovery = None
    recovery_refs: list[TemplateRef] = []
    if decision.recovery_entry:
        recovery = RecoveryEntry(text=renderer.text("pause.recovery_entry"))
        recovery_refs = [TemplateRef(key="pause.recovery_entry")]
    speak = (
        head.refs + numbers.refs + rules.refs + signal_refs + question.refs
        + recovery_refs + explained.cards.speak
    )  # fmt: skip
    fields: dict[str, object] = {
        "level": decision.level,
        "headline": " ".join(head.texts),
        "numbers_text": numbers.texts,
        "rules_text": rules.texts,
        "signals": signals,
        "question": question.texts[0] if question.texts else None,
        "cards": cards,
        "lessons": explained.lessons,
        "recovery_entry": recovery,
        "override_label": renderer.text("pause.override"),
        "decision": decision,
        "event": EventSummary(
            stage=event.stage,
            action=event.action,
            product_class=event.product_class,
            source_type=event.source_type,
        ),
    }
    return PauseContent(
        fields=fields, speak=speak, unverified_fact_ids=explained.unverified_fact_ids
    )
