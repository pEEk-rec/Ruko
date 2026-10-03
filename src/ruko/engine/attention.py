"""Weekly attention budget: caps soft L1 nudges so Ruko stays quiet by default.

Only an L1 whose reasons are *all* low severity can be silenced. L1 nudges with a
medium reason, and every L2 and L3, are never suppressed by the budget.
"""

from __future__ import annotations

from ruko.engine.policy import InterventionPolicy
from ruko.models.common import InterventionLevel, Severity
from ruko.models.decision import AttentionState, Reason
from ruko.models.profile import AttentionCounts


def apply_attention_budget(
    level: InterventionLevel,
    reasons: list[Reason],
    counts: AttentionCounts,
    policy: InterventionPolicy,
) -> tuple[InterventionLevel, AttentionState]:
    """Silence a soft L1 nudge if the weekly budget is used up.

    Args:
        level: Level after decay.
        reasons: Reasons behind it.
        counts: Device-side counts of interventions shown this week.
        policy: Intervention policy (budget size).

    Returns:
        The (possibly lowered) level and the attention-budget state.
    """
    budget = policy.l1_budget_per_week
    soft = level == InterventionLevel.L1 and all(r.severity == Severity.LOW for r in reasons)
    suppressed = soft and counts.l1_this_week >= budget
    state = AttentionState(
        l1_budget_per_week=budget,
        l1_used_this_week=counts.l1_this_week,
        suppressed_by_budget=suppressed,
    )
    return (InterventionLevel.L0 if suppressed else level), state
