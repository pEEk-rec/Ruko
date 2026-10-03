"""Plan matching: decisions planned in advance (while calm) get low friction.

A decision matches a plan when the product class is the same and the amount is inside
the planned range. A plan for the same product class with the amount outside its range
is a deviation. A matching plan with an exit rule also counts as an exit plan.
"""

from __future__ import annotations

from dataclasses import dataclass

from ruko.engine.policy import InterventionPolicy
from ruko.models.common import Certainty, ReasonCode, SignalSource
from ruko.models.event import DecisionEvent, Signal
from ruko.models.profile import PlannedDecision


@dataclass(frozen=True)
class PlanMatch:
    """Result of plan matching."""

    plan: PlannedDecision | None
    deviation: bool


def _fits(event: DecisionEvent, plan: PlannedDecision) -> bool:
    if plan.product_class != event.product_class:
        return False
    if event.amount_inr is None:
        return True
    return plan.amount_min_inr <= event.amount_inr <= plan.amount_max_inr


def match_plan(event: DecisionEvent, plans: list[PlannedDecision]) -> PlanMatch:
    """Find the plan this decision follows, or detect a deviation from one.

    Args:
        event: The decision.
        plans: Plans the user logged in advance.

    Returns:
        A ``PlanMatch``.
    """
    if event.plan_id is not None:
        named = next((p for p in plans if p.id == event.plan_id), None)
        if named is not None:
            return PlanMatch(named, False) if _fits(event, named) else PlanMatch(None, True)
    same_class = [p for p in plans if p.product_class == event.product_class]
    fitting = next((p for p in same_class if _fits(event, p)), None)
    if fitting is not None:
        return PlanMatch(fitting, False)
    return PlanMatch(None, bool(same_class) and event.amount_inr is not None)


def deviation_signal(match: PlanMatch) -> Signal | None:
    """Return ``PLAN_DEVIATION`` when the decision differs from a logged plan."""
    if not match.deviation:
        return None
    return Signal(
        code=ReasonCode.PLAN_DEVIATION, certainty=Certainty.LIKELY, source=SignalSource.RULE
    )


def exit_plan_signal(
    event: DecisionEvent, match: PlanMatch, policy: InterventionPolicy
) -> Signal | None:
    """Return ``NO_EXIT_PLAN`` for risky product classes without an exit plan.

    An explicit "no" is ``likely``; not saying anything is ``possible``.
    """
    if event.product_class not in policy.exit_plan_required_for:
        return None
    if event.has_exit_plan or (match.plan is not None and match.plan.exit_plan is not None):
        return None
    certainty = Certainty.LIKELY if event.has_exit_plan is False else Certainty.POSSIBLE
    return Signal(code=ReasonCode.NO_EXIT_PLAN, certainty=certainty, source=SignalSource.USER)
