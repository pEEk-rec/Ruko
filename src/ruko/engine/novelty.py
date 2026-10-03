"""Novelty and product features: first time with a product class, leverage.

Experience is only what the user declared. If they did not say, Ruko does not assume
they are new (no inference about the person).
"""

from __future__ import annotations

from ruko.engine.policy import InterventionPolicy
from ruko.models.common import Certainty, ReasonCode, SignalSource
from ruko.models.event import DecisionEvent, Signal
from ruko.models.profile import Experience, UserProfile


def first_time_signal(event: DecisionEvent, profile: UserProfile) -> Signal | None:
    """Return ``FIRST_TIME_PRODUCT`` if the user declared no experience with this class."""
    if profile.experience.get(event.product_class) != Experience.NONE:
        return None
    return Signal(
        code=ReasonCode.FIRST_TIME_PRODUCT, certainty=Certainty.LIKELY, source=SignalSource.USER
    )


def leverage_signal(event: DecisionEvent, policy: InterventionPolicy) -> Signal | None:
    """Return ``LEVERAGED_PRODUCT`` for product classes the policy marks as leveraged."""
    if event.product_class not in policy.leveraged_product_classes:
        return None
    certainty = event.field_confidence.get("product_class", Certainty.LIKELY)
    return Signal(code=ReasonCode.LEVERAGED_PRODUCT, certainty=certainty, source=SignalSource.RULE)
