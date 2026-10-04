"""Signals from declared context and from the event's own fields.

- Recent loss and trading frequency come only from the user's declaration.
- Unsolicited source and payment to an individual come from the event fields, which
  the user may have set or the understanding layer extracted (with a certainty).
"""

from __future__ import annotations

from ruko.engine.policy import InterventionPolicy
from ruko.models.common import (
    Certainty,
    PaymentDestination,
    ReasonCode,
    SignalSource,
    SourceType,
)
from ruko.models.event import DecisionEvent, Signal
from ruko.models.profile import UserProfile


def declared_context_signals(profile: UserProfile, policy: InterventionPolicy) -> list[Signal]:
    """Signals from what the user said about their recent behaviour."""
    found: list[Signal] = []
    if profile.recent.post_loss:
        found.append(
            Signal(
                code=ReasonCode.POST_LOSS_REENTRY_DECLARED,
                certainty=Certainty.LIKELY,
                source=SignalSource.USER,
            )
        )
    if profile.recent.late_night:
        found.append(
            Signal(
                code=ReasonCode.LATE_NIGHT_DECISION,
                certainty=Certainty.LIKELY,
                source=SignalSource.RULE,
            )
        )
    if profile.recent.trades_this_week in policy.high_frequency_bands:
        found.append(
            Signal(
                code=ReasonCode.HIGH_FREQUENCY_DECLARED,
                certainty=Certainty.LIKELY,
                source=SignalSource.USER,
            )
        )
    return found


def event_field_signals(event: DecisionEvent) -> list[Signal]:
    """Signals implied by the event's source type and payment destination fields."""
    found: list[Signal] = []
    if event.source_type == SourceType.UNSOLICITED_GROUP:
        certainty = event.field_confidence.get("source_type", Certainty.LIKELY)
        found.append(
            Signal(
                code=ReasonCode.UNSOLICITED_SOURCE, certainty=certainty, source=SignalSource.RULE
            )
        )
    if event.payment_destination == PaymentDestination.INDIVIDUAL_ACCOUNT:
        certainty = event.field_confidence.get("payment_destination", Certainty.POSSIBLE)
        found.append(
            Signal(
                code=ReasonCode.PAY_TO_INDIVIDUAL_ACCOUNT,
                certainty=certainty,
                source=SignalSource.RULE,
            )
        )
    return found
