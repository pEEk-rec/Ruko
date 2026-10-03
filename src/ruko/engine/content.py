"""Summarise the content dimension: what the message itself shows.

Severity and count come from the policy file; certainty is the strongest certainty among
the signals. This summary is shown as-is in content reports; it is never a verdict.
"""

from __future__ import annotations

from dataclasses import dataclass

from ruko.engine.policy import InterventionPolicy
from ruko.models.common import Certainty, ReasonCode, Severity, dimension_of
from ruko.models.decision import Reason

_STRENGTH = {Certainty.UNCLEAR: 0, Certainty.POSSIBLE: 1, Certainty.LIKELY: 2}


@dataclass(frozen=True)
class ContentSummary:
    """Highest severity, corroborating medium-or-higher count, and certainty."""

    codes: tuple[ReasonCode, ...]
    highest: Severity | None
    medium_or_higher: int
    certainty: Certainty | None


def summarize_content(reasons: list[Reason], policy: InterventionPolicy) -> ContentSummary:
    """Aggregate the content reasons of a decision."""
    content = [r for r in reasons if dimension_of(r.code).value == "content"]
    if not content:
        return ContentSummary((), None, 0, None)
    highest = max((policy.severity(r.code) for r in content), key=lambda s: s.rank)
    medium = sum(policy.severity(r.code).rank >= Severity.MEDIUM.rank for r in content)
    certainty = max((r.certainty for r in content), key=lambda c: _STRENGTH[c])
    return ContentSummary(tuple(r.code for r in content), highest, medium, certainty)
