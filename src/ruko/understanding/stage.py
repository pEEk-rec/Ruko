"""Decision-stage classification (CLAUDE.md 1.2), deterministic first.

Every input is classified into one of seven stages, and the stage decides the path:
``learn`` (glossary), ``evaluate_content`` (content report), ``consider_action`` and
``about_to_act`` (engine), ``already_acted`` (recovery), ``calculate`` (calculator,
CLAUDE.md 1.5), ``unknown`` (one question).

Order of evidence:

1. A stage the user chose in the app wins.
2. Patterns from ``data/stages/*.yaml`` (every language runs on every input).
   Tie-breaks: ``already_acted`` together with a pre-decision stage (consider / about to
   act) is ambiguous, so Ruko asks (``unknown``). Otherwise the most specific path wins:
   already_acted > about_to_act > calculate > consider_action > evaluate_content > learn.
   (An explicit calculation question wins over "thinking of investing"; acting right now
   still gets the pause.)
3. No pattern: a declared amount means ``consider_action``; shared content that looks
   financial (product hints or message signals) is treated as a decision being
   considered; anything else is ``unknown``.
4. The LLM may fill the stage only when the deterministic result is ``unknown``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from ruko.data_files import data_dir, load_yaml
from ruko.guardrails.normalize import normalize, strip_zero_width
from ruko.models.common import DecisionStage, PaymentDestination
from ruko.models.event import StageResult
from ruko.models.requests import PaymentMethod, RecoveryAnswers

_FLAGS = re.IGNORECASE | re.UNICODE
PRIORITY = (
    DecisionStage.ALREADY_ACTED,
    DecisionStage.ABOUT_TO_ACT,
    DecisionStage.CALCULATE,
    DecisionStage.CONSIDER_ACTION,
    DecisionStage.EVALUATE_CONTENT,
    DecisionStage.LEARN,
)
PRE_DECISION = frozenset({DecisionStage.CONSIDER_ACTION, DecisionStage.ABOUT_TO_ACT})
PATTERN_CONFIDENCE = 0.8
DEFAULT_CONFIDENCE = 0.6


@dataclass(frozen=True)
class StagePatterns:
    """Compiled stage patterns and recovery hints from every locale."""

    stages: dict[DecisionStage, tuple[re.Pattern[str], ...]]
    hints: dict[str, tuple[re.Pattern[str], ...]]


def _compile(patterns: list[str]) -> list[re.Pattern[str]]:
    return [re.compile(strip_zero_width(p), _FLAGS) for p in patterns]


@lru_cache(maxsize=1)
def get_stage_patterns() -> StagePatterns:
    """Load every ``data/stages/*.yaml`` file (cached)."""
    stages: dict[DecisionStage, list[re.Pattern[str]]] = {s: [] for s in PRIORITY}
    hints: dict[str, list[re.Pattern[str]]] = {}
    for path in sorted((data_dir() / "stages").glob("*.yaml")):
        raw = load_yaml("stages", path.name)
        for name, patterns in raw["stages"].items():
            stages[DecisionStage(name)] += _compile(patterns)
        for name, patterns in (raw.get("recovery_hints") or {}).items():
            hints.setdefault(name, []).extend(_compile(patterns))
    return StagePatterns(
        stages={k: tuple(v) for k, v in stages.items()},
        hints={k: tuple(v) for k, v in hints.items()},
    )


def matched_stages(text: str) -> set[DecisionStage]:
    """Return every stage whose patterns match the text."""
    normalized = normalize(text)
    patterns = get_stage_patterns().stages
    return {stage for stage, pats in patterns.items() if any(p.search(normalized) for p in pats)}


def resolve(matched: set[DecisionStage]) -> DecisionStage | None:
    """Apply the tie-break rules; ``unknown`` when already-acted conflicts with acting."""
    if DecisionStage.ALREADY_ACTED in matched and matched & PRE_DECISION:
        return DecisionStage.UNKNOWN
    return next((stage for stage in PRIORITY if stage in matched), None)


def classify_stage(
    text: str,
    *,
    declared: DecisionStage | None = None,
    declared_amount: bool = False,
    looks_financial: bool = False,
) -> StageResult:
    """Classify the decision stage of an input.

    Args:
        text: The raw input text (patterns run in memory only).
        declared: A stage the user chose in the app (wins).
        declared_amount: The user declared an amount for this decision.
        looks_financial: Deterministic understanding found product hints or signals.

    Returns:
        The stage with its confidence and source.
    """
    if declared is not None:
        return StageResult(stage=declared, confidence=1.0, source="user")
    stage = resolve(matched_stages(text))
    if stage is not None:
        confidence = 0.0 if stage == DecisionStage.UNKNOWN else PATTERN_CONFIDENCE
        return StageResult(stage=stage, confidence=confidence, source="lexicon")
    if declared_amount:
        return StageResult(stage=DecisionStage.CONSIDER_ACTION, confidence=1.0, source="user")
    if looks_financial:
        return StageResult(
            stage=DecisionStage.CONSIDER_ACTION, confidence=DEFAULT_CONFIDENCE, source="default"
        )
    return StageResult(stage=DecisionStage.UNKNOWN, confidence=0.0, source="default")


def recovery_answers_from_text(
    text: str, payment_destination: PaymentDestination = PaymentDestination.UNKNOWN
) -> RecoveryAnswers:
    """Pre-fill recovery answers from an ``already_acted`` report (the user can correct them).

    Never extracts amounts, IDs or account numbers: only yes/no facts and the payment method.
    """
    normalized = normalize(text)
    hints = get_stage_patterns().hints

    def has(name: str) -> bool:
        return any(p.search(normalized) for p in hints.get(name, ()))

    method = PaymentMethod.NONE
    if has("paid_money"):
        method = PaymentMethod.CASH_OR_OTHER
        for name, value in (("payment_upi", PaymentMethod.UPI),
                            ("payment_bank", PaymentMethod.BANK_TRANSFER),
                            ("payment_card", PaymentMethod.CARD)):  # fmt: skip
            if has(name):
                method = value
                break
        if method == PaymentMethod.CASH_OR_OTHER and payment_destination.value != "unknown":
            method = PaymentMethod.UPI
    return RecoveryAnswers(
        paid_money=has("paid_money"),
        payment_method=method,
        installed_app=has("installed_app"),
        registered_broker_involved=has("registered_broker_involved") and not has("paid_money"),
        unauthorized_trade=has("unauthorized_trade"),
        cannot_withdraw=has("cannot_withdraw"),
    )
