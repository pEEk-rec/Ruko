"""Friction decay: a run of rule-following decisions fades novelty-only nudges.

If the only reasons that raise the level are novelty (first time with a product class)
and the user's streak of rule-following decisions has reached the threshold, an L1
becomes L0. This is how Ruko steps back as the user needs it less.
"""

from __future__ import annotations

from ruko.engine.policy import InterventionPolicy
from ruko.models.common import InterventionLevel, ReasonCode


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
    raising = {c for c in codes if policy.codes[c].solo_level != InterventionLevel.L0}
    decayable = policy.codes_in(policy.decay_categories)
    if raising and raising <= decayable:
        return InterventionLevel.L0, True
    return level, False
