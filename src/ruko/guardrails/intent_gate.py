"""Input intent gate: decides whether Ruko must refuse an input before anything else runs.

Order of checks:

1. Sensitive data (OTP, PIN, CVV, password, card, own account number): refuse and warn.
2. Deterministic refusal patterns (all languages, normal + de-obfuscated text).
3. Optional second opinion (an LLM classifier behind the provider interface). It can
   **add** a refusal class but can never remove one found by the patterns.

The gate also records two non-refusing flags: ``verdict_requested`` ("is this a scam?")
and ``injection_suspected`` (text that addresses an AI). Neither changes what Ruko
computes; content is always treated as data.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from ruko.guardrails.normalize import deobfuscate, normalize
from ruko.guardrails.policy import GuardrailPolicy, get_policy
from ruko.guardrails.sensitive import detect_sensitive
from ruko.models.common import RefusalClass

SecondOpinion = Callable[[str], Iterable[RefusalClass]]
"""A classifier that returns refusal classes for (already redacted) text."""


@dataclass(frozen=True)
class GateResult:
    """Outcome of the intent gate. Contains class names and flags, never content."""

    refusal_class: RefusalClass | None
    matched_classes: tuple[RefusalClass, ...] = ()
    sensitive_types: tuple[str, ...] = ()
    verdict_requested: bool = False
    injection_suspected: bool = False
    added_by_second_opinion: tuple[RefusalClass, ...] = field(default_factory=tuple)

    @property
    def refused(self) -> bool:
        """Return True if the input must not be processed further."""
        return self.refusal_class is not None


def _any_match(patterns: Iterable[re.Pattern[str]], variants: tuple[str, ...]) -> bool:
    return any(p.search(text) for p in patterns for text in variants)


def _pattern_classes(variants: tuple[str, ...], policy: GuardrailPolicy) -> list[RefusalClass]:
    return [
        rule.refusal_class for rule in policy.refusal_rules if _any_match(rule.patterns, variants)
    ]


def _ask_second_opinion(second_opinion: SecondOpinion | None, text: str) -> set[RefusalClass]:
    if second_opinion is None:
        return set()
    try:
        return {RefusalClass(c) for c in second_opinion(text)}
    except Exception:  # noqa: BLE001 - the deterministic result stands on its own
        return set()


def check_intent(
    text: str,
    *,
    second_opinion: SecondOpinion | None = None,
    second_opinion_text: str | None = None,
    policy: GuardrailPolicy | None = None,
) -> GateResult:
    """Classify an input and decide whether it must be refused.

    Args:
        text: The raw input text (checked in memory, never stored).
        second_opinion: Optional classifier that may add refusal classes.
        second_opinion_text: Redacted text to send to the second opinion (never raw text).
        policy: Optional policy override.

    Returns:
        A ``GateResult``; ``refusal_class`` is set when Ruko must refuse.
    """
    policy = policy or get_policy()
    sensitive = tuple(detect_sensitive(text, policy))
    if sensitive:
        return GateResult(
            refusal_class=RefusalClass.SENSITIVE_DATA_SUBMISSION,
            matched_classes=(RefusalClass.SENSITIVE_DATA_SUBMISSION,),
            sensitive_types=sensitive,
        )

    normalized = normalize(text)
    variants = (normalized, deobfuscate(normalized))
    matched = _pattern_classes(variants, policy)
    extra = _ask_second_opinion(second_opinion, second_opinion_text or "") - set(matched)
    extra.discard(RefusalClass.SENSITIVE_DATA_SUBMISSION)
    ordered_extra = [r.refusal_class for r in policy.refusal_rules if r.refusal_class in extra]
    all_classes = tuple(matched + ordered_extra)

    return GateResult(
        refusal_class=all_classes[0] if all_classes else None,
        matched_classes=all_classes,
        verdict_requested=_any_match(policy.verdict_patterns, variants),
        injection_suspected=_any_match(policy.injection_patterns, variants),
        added_by_second_opinion=tuple(ordered_extra),
    )
