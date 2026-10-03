"""Decision plans: planned decisions get low friction; plans are asked for, never required.

- A decision matches a prior plan when the product class is the same and the amount is
  inside the planned range (or the device says it follows one). No plan reason is raised.
- A prior plan for the same class with the amount outside its range: ``PLAN_DEVIATION``.
- For classes where a plan is expected (derivatives, crypto) and no prior plan matches:
  no plan given at all is ``UNPLANNED_DECISION``; a plan missing its reason, horizon or
  reconsider condition is ``PLAN_INCOMPLETE``. Both are mild (at most a nudge alone).
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


def plan_signal(
    event: DecisionEvent, match: PlanMatch, policy: InterventionPolicy
) -> Signal | None:
    """Return ``UNPLANNED_DECISION`` or ``PLAN_INCOMPLETE`` where a plan is expected."""
    if event.product_class not in policy.plan_expected_for or match.plan or match.deviation:
        return None
    plan = event.plan
    if plan is not None and (plan.matches_prior_plan or plan.complete):
        return None
    if plan is None or not plan.started:
        return Signal(
            code=ReasonCode.UNPLANNED_DECISION,
            certainty=Certainty.POSSIBLE,
            source=SignalSource.USER,
        )
    return Signal(
        code=ReasonCode.PLAN_INCOMPLETE, certainty=Certainty.LIKELY, source=SignalSource.USER
    )
