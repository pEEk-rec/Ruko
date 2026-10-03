"""The user's own rules, checked against this decision.

Each check returns a ``Signal`` (code + certainty + source). Certainty is honest about
bands: a breach that holds across the whole band is ``likely``; one that holds only at
the band's typical value is ``possible``.
"""

from __future__ import annotations

from ruko.models.common import Certainty, FundingSource, ReasonCode, SignalSource
from ruko.models.decision import ExposureNumbers
from ruko.models.event import DecisionEvent, Signal
from ruko.models.profile import UserProfile


def _signal(code: ReasonCode, certainty: Certainty, source: SignalSource) -> Signal:
    return Signal(code=code, certainty=certainty, source=source)


def max_share_rule(profile: UserProfile, numbers: ExposureNumbers) -> Signal | None:
    """Flag when the amount is a bigger share of savings than the user's own maximum."""
    limit = profile.rules.max_share_of_savings_pct
    share = numbers.share_of_savings_pct
    if limit is None or share is None or share.typical <= limit:
        return None
    certainty = Certainty.LIKELY if share.low > limit else Certainty.POSSIBLE
    return _signal(ReasonCode.RULE_MAX_SHARE_EXCEEDED, certainty, SignalSource.RULE)


def max_amount_rule(event: DecisionEvent, profile: UserProfile) -> Signal | None:
    """Flag when the amount is above the user's own per-decision maximum."""
    limit = profile.rules.max_amount_inr
    if limit is None or event.amount_inr is None or event.amount_inr <= limit:
        return None
    return _signal(ReasonCode.RULE_MAX_AMOUNT_EXCEEDED, Certainty.LIKELY, SignalSource.RULE)


def funding_rules(event: DecisionEvent) -> list[Signal]:
    """Flag borrowed, protected-goal and emergency money, as declared by the user."""
    by_source = {
        FundingSource.BORROWED: ReasonCode.BORROWED_FUNDS,
        FundingSource.PROTECTED_GOAL: ReasonCode.PROTECTED_GOAL_FUNDS,
        FundingSource.EMERGENCY_FUND: ReasonCode.EMERGENCY_FUNDS,
    }
    code = by_source.get(event.funding_source)
    return [_signal(code, Certainty.LIKELY, SignalSource.USER)] if code else []


def emergency_buffer_rule(profile: UserProfile, numbers: ExposureNumbers) -> Signal | None:
    """Flag when savings left would fall below the emergency buffer the user set."""
    target = profile.emergency_buffer_months
    left = numbers.remaining_buffer_months
    if target is None or left is None or left.typical >= target:
        return None
    certainty = Certainty.LIKELY if left.high < target else Certainty.POSSIBLE
    return _signal(ReasonCode.EMERGENCY_FUNDS, certainty, SignalSource.RULE)


def evaluate_rules(
    event: DecisionEvent, profile: UserProfile, numbers: ExposureNumbers
) -> list[Signal]:
    """Run every personal-rule check.

    Args:
        event: The decision.
        profile: The device snapshot with the user's rules.
        numbers: Personal numbers from ``exposure.compute_numbers``.

    Returns:
        Signals for every rule that this decision breaks.
    """
    found = [
        max_share_rule(profile, numbers),
        max_amount_rule(event, profile),
        emergency_buffer_rule(profile, numbers),
    ]
    return [s for s in found if s is not None] + funding_rules(event)
