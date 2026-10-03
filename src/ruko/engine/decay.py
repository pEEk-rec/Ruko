"""Friction decay: a run of rule-following decisions fades novelty-only nudges.

If the level is L1, there are no content signals, and every behavioural trigger is
novelty (first time with a product class), a streak of rule-following decisions at or
above the threshold makes it L0. Decay never touches content signals or L2/L3.
"""

from __future__ import annotations

from ruko.engine.policy import InterventionPolicy
from ruko.models.common import Dimension, InterventionLevel, ReasonCode, dimension_of


def apply_decay(
    level: InterventionLevel,
    codes: set[ReasonCode],
    streak: int,
    policy: InterventionPolicy,
) -> tuple[InterventionLevel, bool]:
    """Fade a novelty-only L1 to L0 after a good streak.

    Args:
        level: Computed level.
        codes: Reason codes present.
        streak: Consecutive past decisions that followed the user's rules.
        policy: Intervention policy (threshold, decay categories).

    Returns:
        The (possibly lowered) level and whether decay was applied.
    """
    if level != InterventionLevel.L1 or streak < policy.decay_streak_threshold:
        return level, False
    if any(dimension_of(c) == Dimension.CONTENT for c in codes):
        return level, False
    triggers = {c for c in codes if policy.category(c) in policy.behavioural_trigger_categories}
    if triggers and all(policy.category(c) in policy.decay_categories for c in triggers):
        return InterventionLevel.L0, True
    return level, False
