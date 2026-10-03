"""Map a set of reason codes to an intervention level using the policy table.

level = max(solo level of each code, level of each matching combination rule)

Because it is a maximum, adding a reason can never lower the computed level.
"""

from __future__ import annotations

from collections.abc import Iterable

from ruko.engine.policy import Combination, InterventionPolicy
from ruko.models.common import InterventionLevel, ReasonCode


def _max_level(levels: Iterable[InterventionLevel]) -> InterventionLevel:
    return max(levels, key=lambda lvl: lvl.rank, default=InterventionLevel.L0)


def solo_level(codes: set[ReasonCode], policy: InterventionPolicy) -> InterventionLevel:
    """Return the highest solo level among the codes (L0 if there are none)."""
    return _max_level(policy.codes[c].solo_level for c in codes)


def matching_combinations(codes: set[ReasonCode], policy: InterventionPolicy) -> list[Combination]:
    """Return the combination rules satisfied by the codes."""
    return [rule for rule in policy.combinations if len(codes & set(rule.codes)) >= rule.min_count]


def compute_level(codes: set[ReasonCode], policy: InterventionPolicy) -> InterventionLevel:
    """Return the computed level for a set of codes (before budget and decay)."""
    combos = (rule.level for rule in matching_combinations(codes, policy))
    return _max_level([solo_level(codes, policy), *combos])
