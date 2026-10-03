"""Map reasons to an intervention level with the level rules in the policy file.

Each rule says "when these conditions hold, the level is at least X". The level is the
highest X of all matching rules (L0 if none), so adding a reason can never lower it.
The same rules also give a level per dimension: content-only rules on the message
signals, behaviour-only rules on the user's context. Mixed rules count only in the
combined level.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ruko.engine.policy import InterventionPolicy, LevelRule
from ruko.models.common import Dimension, InterventionLevel, ReasonCode, dimension_of


@dataclass(frozen=True)
class LevelResult:
    """Combined level, level per dimension, and the rules that matched."""

    level: InterventionLevel
    content: InterventionLevel
    behavioural: InterventionLevel
    matched: tuple[str, ...]


def _max_level(levels: Iterable[InterventionLevel]) -> InterventionLevel:
    return max(levels, key=lambda lvl: lvl.rank, default=InterventionLevel.L0)


def _content_ok(rule: LevelRule, codes: set[ReasonCode], policy: InterventionPolicy) -> bool:
    if rule.content_severity is None:
        return True
    strong = {
        c for c in codes
        if dimension_of(c) == Dimension.CONTENT
        and policy.severity(c).rank >= rule.content_severity.rank
    }  # fmt: skip
    return len(strong) >= rule.content_count


def _behaviour_ok(rule: LevelRule, codes: set[ReasonCode], policy: InterventionPolicy) -> bool:
    behavioural = {c for c in codes if dimension_of(c) == Dimension.BEHAVIOURAL}
    categories = [policy.category(c) for c in behavioural]
    if rule.any_category and not rule.any_category & set(categories):
        return False
    counted = sum(cat in rule.count_categories for cat in categories)
    if rule.count_categories and counted < rule.count_in_categories:
        return False
    if rule.all_of_codes and not rule.all_of_codes <= codes:
        return False
    triggers = policy.behavioural_trigger_categories
    return not (rule.behavioural_trigger and not set(categories) & triggers)


def rule_matches(rule: LevelRule, codes: set[ReasonCode], policy: InterventionPolicy) -> bool:
    """Return True if every condition of the rule holds for these codes."""
    return _content_ok(rule, codes, policy) and _behaviour_ok(rule, codes, policy)


def compute_levels(codes: set[ReasonCode], policy: InterventionPolicy) -> LevelResult:
    """Return the combined level and the level of each dimension for a set of codes."""
    matched = [r for r in policy.level_rules if rule_matches(r, codes, policy)]
    content_only = [r.level for r in matched if r.uses_content and not r.uses_behaviour]
    behaviour_only = [r.level for r in matched if r.uses_behaviour and not r.uses_content]
    return LevelResult(
        level=_max_level(r.level for r in matched),
        content=_max_level(content_only),
        behavioural=_max_level(behaviour_only),
        matched=tuple(r.id for r in matched),
    )


def compute_level(codes: set[ReasonCode], policy: InterventionPolicy) -> InterventionLevel:
    """Return the combined level for a set of codes (before budget and decay)."""
    return compute_levels(codes, policy).level
