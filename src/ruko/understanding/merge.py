"""Combine deterministic findings, LLM fields and the user's answers into a ``DecisionEvent``.

Sources, from most to least trusted:

1. **The user's answers** always win (amount and funding source come only from here).
2. **Deterministic findings** (lexicon, link analyzer, payment classifier) are never
   removed or weakened by the LLM.
3. **The LLM** can add and corroborate. One simple rule for disagreement:

   - both agree -> the value, certainty ``likely`` (signals: the stronger certainty)
   - only the deterministic side found it -> kept as it is
   - only the LLM found it -> kept, with certainty one step lower than the LLM said
   - they disagree on a field -> ``unknown`` with certainty ``unclear`` (for the product
     class, the user is then asked)

Every disagreement is recorded as a content-free ``MergeNote``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ruko.models.common import (
    Certainty,
    FundingSource,
    HoldingIntent,
    PaymentDestination,
    ProductClass,
    ReasonCode,
    SourceType,
)
from ruko.models.event import DecisionEvent, Signal
from ruko.models.requests import DecisionAnswers
from ruko.understanding.extract import ExtractionOutcome
from ruko.understanding.lexicon import detect_hints, detect_signals
from ruko.understanding.links import link_signals
from ruko.understanding.payments import analyze_payments, payment_destination, payment_signals

_STRENGTH = {Certainty.LIKELY: 2, Certainty.POSSIBLE: 1, Certainty.UNCLEAR: 0}
_LOWER = {
    Certainty.LIKELY: Certainty.POSSIBLE,
    Certainty.POSSIBLE: Certainty.UNCLEAR,
    Certainty.UNCLEAR: Certainty.UNCLEAR,
}
_HINT_FIELDS: dict[str, type[ProductClass] | type[SourceType] | type[HoldingIntent]] = {
    "product_class": ProductClass,
    "source_type": SourceType,
    "holding_intent": HoldingIntent,
}


@dataclass(frozen=True)
class DeterministicFindings:
    """Everything found without the LLM. Contains codes and enum values, never text."""

    signals: tuple[Signal, ...]
    hints: dict[str, tuple[str, ...]]
    payment_destination: PaymentDestination


@dataclass(frozen=True)
class MergeNote:
    """A recorded disagreement between sources (a field name or reason code, no content)."""

    subject: str
    kind: Literal["llm_only", "deterministic_only", "conflict"]


@dataclass(frozen=True)
class Understanding:
    """The merged view of the message, before the user's answers are applied."""

    event: DecisionEvent
    notes: tuple[MergeNote, ...]


def _stronger(a: Certainty, b: Certainty) -> Certainty:
    return a if _STRENGTH[a] >= _STRENGTH[b] else b


def _keep_strongest(signals: list[Signal]) -> list[Signal]:
    best: dict[ReasonCode, Signal] = {}
    for signal in signals:
        current = best.get(signal.code)
        if current is None or _STRENGTH[signal.certainty] > _STRENGTH[current.certainty]:
            best[signal.code] = signal
    return list(best.values())


def collect_deterministic(redacted_text: str) -> DeterministicFindings:
    """Run the lexicon, link analyzer and payment classifier on redacted text."""
    findings = analyze_payments(redacted_text)
    signals = detect_signals(redacted_text)
    signals += link_signals(redacted_text)[0]
    signals += payment_signals(findings)
    hints = {name: tuple(values) for name, values in detect_hints(redacted_text).items()}
    return DeterministicFindings(
        signals=tuple(_keep_strongest(signals)),
        hints=hints,
        payment_destination=payment_destination(findings),
    )


def _merge_signals(
    deterministic: tuple[Signal, ...], llm: tuple[Signal, ...], llm_ran: bool
) -> tuple[list[Signal], list[MergeNote]]:
    by_code = {s.code: s for s in deterministic}
    merged: list[Signal] = []
    notes: list[MergeNote] = []
    for signal in deterministic:
        agreeing = next((s for s in llm if s.code == signal.code), None)
        if agreeing is None:
            merged.append(signal)
            if llm_ran:
                notes.append(MergeNote(signal.code.value, "deterministic_only"))
            continue
        certainty = _stronger(signal.certainty, agreeing.certainty)
        merged.append(signal.model_copy(update={"certainty": certainty}))
    for signal in llm:
        if signal.code not in by_code:
            merged.append(signal.model_copy(update={"certainty": _LOWER[signal.certainty]}))
            notes.append(MergeNote(signal.code.value, "llm_only"))
    return merged, notes


def _merge_field(
    name: str, candidates: tuple[str, ...], llm_value: str | None, llm_conf: Certainty | None
) -> tuple[str | None, Certainty | None, MergeNote | None]:
    """Return (value, certainty, note) for one categorical field. ``None`` means unknown."""
    if llm_value is not None and candidates:
        if llm_value in candidates:
            return llm_value, Certainty.LIKELY if len(candidates) == 1 else Certainty.POSSIBLE, None
        return None, Certainty.UNCLEAR, MergeNote(name, "conflict")
    if llm_value is not None:
        return llm_value, _LOWER[llm_conf or Certainty.POSSIBLE], MergeNote(name, "llm_only")
    if candidates:
        certainty = Certainty.POSSIBLE if len(candidates) == 1 else Certainty.UNCLEAR
        return candidates[0], certainty, None
    return None, None, None


def merge(findings: DeterministicFindings, outcome: ExtractionOutcome) -> Understanding:
    """Combine deterministic findings with the LLM outcome (either may be empty).

    Args:
        findings: Output of ``collect_deterministic``.
        outcome: Output of ``extract`` (``lexicon_only`` mode has no LLM fields).

    Returns:
        The merged ``DecisionEvent`` (amount and funding still unknown) and notes.
    """
    llm = outcome.extraction if outcome.mode == "llm" else None
    signals, notes = _merge_signals(
        findings.signals, outcome.signals if llm else (), llm_ran=llm is not None
    )
    values: dict[str, object] = {}
    confidence: dict[str, Certainty] = {}

    for name, enum_type in _HINT_FIELDS.items():
        llm_value = getattr(llm, name).value if llm else None
        llm_value = None if llm_value == "unknown" else llm_value
        llm_conf = llm.field_confidence.get(name) if llm else None
        value, certainty, note = _merge_field(
            name, findings.hints.get(name, ()), llm_value, llm_conf
        )
        if note:
            notes.append(note)
        if value is not None:
            values[name] = enum_type(value)
        if certainty is not None:
            confidence[name] = certainty

    individual = PaymentDestination.INDIVIDUAL_ACCOUNT
    llm_individual = bool(llm and llm.payment_destination == individual)
    if findings.payment_destination == individual:
        values["payment_destination"] = individual
        confidence["payment_destination"] = Certainty.LIKELY
    elif llm_individual and llm is not None:
        values["payment_destination"] = individual
        stated = llm.field_confidence.get("payment_destination", Certainty.POSSIBLE)
        confidence["payment_destination"] = _LOWER[stated]
        notes.append(MergeNote("payment_destination", "llm_only"))

    deterministic_financial = bool(findings.hints.get("product_class") or findings.signals)
    is_financial = deterministic_financial or bool(llm and llm.is_financial_decision)
    if llm and deterministic_financial and not llm.is_financial_decision:
        notes.append(MergeNote("is_financial_decision", "conflict"))

    event = DecisionEvent.model_validate(
        {
            "is_financial_decision": is_financial,
            "signals": signals,
            "field_confidence": confidence,
            **values,
        }
    )
    return Understanding(event=event, notes=tuple(notes))


def apply_answers(event: DecisionEvent, answers: DecisionAnswers) -> DecisionEvent:
    """Overlay the user's own answers. They always win; amount/funding come only from here."""
    update: dict[str, object] = {}
    confidence = dict(event.field_confidence)
    for name in ("product_class", "source_type", "holding_intent"):
        value = getattr(answers, name)
        if value is not None:
            update[name] = value
            confidence[name] = Certainty.LIKELY
    if answers.amount_inr is not None:
        update["amount_inr"] = answers.amount_inr
        update["is_financial_decision"] = True
    if answers.funding_source is not None:
        update["funding_source"] = answers.funding_source
        if answers.funding_source != FundingSource.UNKNOWN:
            update["is_financial_decision"] = True
    if answers.funding_source == FundingSource.PROTECTED_GOAL:
        update["protected_goal_id"] = answers.protected_goal_id
    for name in ("has_exit_plan", "plan_id"):
        if getattr(answers, name) is not None:
            update[name] = getattr(answers, name)
    update["field_confidence"] = confidence
    return DecisionEvent.model_validate({**event.model_dump(), **update})
