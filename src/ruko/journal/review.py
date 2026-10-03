"""Stateless journal review: the user's own patterns, computed for one request.

The device sends its journal; the server returns numbers and rendered template text and
keeps nothing. The patterns follow ``docs/impact_metrics.md``:

- share of decisions that started from unsolicited sources (group tips, influencers)
- plans written, and plans followed (where the user logged it)
- pauses: read through (completion), understood (comprehension), reconsidered
- overrides with a reason vs without (overrides are fine; unexplained ones are a signal)
- growth of the user's own written rules and plans over time
- interventions per decision per week, shown but never treated as success on its own

No score, no ranking, no comparison with other people, no judgement of outcomes.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from functools import lru_cache

from ruko.data_files import load_yaml
from ruko.language.templates import Renderer
from ruko.models.common import InterventionLevel, SourceType
from ruko.models.journal import (
    RECONSIDERED,
    JournalEntry,
    JournalReviewResponse,
    Trend,
    WeekPoint,
)
from ruko.models.responses import ResponseMeta, TemplateRef

_HIGHLIGHTS = (
    "unsolicited", "plans_set", "plans_followed", "pause_completion", "comprehension",
    "reconsideration",
)  # fmt: skip
TEMPLATE_KEYS = frozenset(
    {
        "journal.empty",
        "journal.too_few",
        "journal.highlight.overrides",
        *(f"journal.highlight.{name}" for name in _HIGHLIGHTS),
        *(f"journal.articulation.{t}" for t in ("growing", "steady", "shrinking")),
        "journal.articulation.not_enough_data",
    }
)
"""Every template key the review can render (checked by the template linter)."""


@dataclass(frozen=True)
class JournalPolicy:
    """Settings from ``data/policy/journal.yaml``."""

    tip_sources: frozenset[SourceType]
    intervention_levels: frozenset[InterventionLevel]
    pause_levels: frozenset[InterventionLevel]
    weeks_window: int
    min_entries_for_patterns: int


@lru_cache(maxsize=1)
def get_journal_policy() -> JournalPolicy:
    """Load the journal policy (cached)."""
    raw = load_yaml("policy", "journal.yaml")
    return JournalPolicy(
        tip_sources=frozenset(SourceType(s) for s in raw["tip_source_types"]),
        intervention_levels=frozenset(InterventionLevel(x) for x in raw["intervention_levels"]),
        pause_levels=frozenset(InterventionLevel(x) for x in raw["pause_levels"]),
        weeks_window=int(raw["weeks_window"]),
        min_entries_for_patterns=int(raw["min_entries_for_patterns"]),
    )


def percent(part: int, whole: int) -> float | None:
    """Return part/whole as a percentage with one decimal, or None when whole is 0."""
    return None if whole == 0 else round(100 * part / whole, 1)


def week_start(day: dt.date) -> dt.date:
    """Return the Monday of the week containing ``day``."""
    return day - dt.timedelta(days=day.weekday())


def weekly_points(
    entries: list[JournalEntry], as_of: dt.date, policy: JournalPolicy
) -> list[WeekPoint]:
    """Interventions per decision for each week in the window that has decisions."""
    first_week = week_start(as_of) - dt.timedelta(weeks=policy.weeks_window - 1)
    weeks: dict[dt.date, list[JournalEntry]] = {}
    for entry in entries:
        start = week_start(entry.date)
        if start >= first_week:
            weeks.setdefault(start, []).append(entry)
    points = []
    for start in sorted(weeks):
        items = weeks[start]
        stepped_in = sum(e.level_shown in policy.intervention_levels for e in items)
        points.append(
            WeekPoint(
                week_start=start,
                decisions=len(items),
                interventions=stepped_in,
                per_decision=round(stepped_in / len(items), 3),
            )
        )
    return points


def _articulated(entry: JournalEntry) -> int | None:
    if entry.own_rules_count is None and entry.own_plans_count is None:
        return None
    return (entry.own_rules_count or 0) + (entry.own_plans_count or 0)


def rule_articulation(entries: list[JournalEntry]) -> tuple[int | None, int | None, Trend]:
    """Compare written rules (+ plans) at the first and the latest entry that records them."""
    counted = [e for e in sorted(entries, key=lambda e: e.date) if _articulated(e) is not None]
    if len(counted) < 2:
        return None, None, "not_enough_data"
    first, latest = counted[0], counted[-1]
    before, after = _articulated(first) or 0, _articulated(latest) or 0
    trend: Trend = "growing" if after > before else "shrinking" if after < before else "steady"
    return first.own_rules_count, latest.own_rules_count, trend


def _fmt(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".")


def _highlights(review: JournalReviewResponse, policy: JournalPolicy) -> list[TemplateRef]:
    if review.total_decisions == 0:
        return [TemplateRef(key="journal.empty")]
    refs: list[TemplateRef] = []
    if review.total_decisions < policy.min_entries_for_patterns:
        refs.append(TemplateRef(key="journal.too_few"))
    values = (
        review.unsolicited_share_pct, review.plans_set_pct, review.plans_followed_pct,
        review.pause_completion_pct, review.comprehension_pct, review.reconsideration_pct,
    )  # fmt: skip
    for name, value in zip(_HIGHLIGHTS, values, strict=True):
        if value is not None:
            refs.append(TemplateRef(key=f"journal.highlight.{name}", slots={"pct": _fmt(value)}))
    if review.overrides_with_reason + review.overrides_without_reason:
        slots = {
            "with_reason": str(review.overrides_with_reason),
            "without_reason": str(review.overrides_without_reason),
        }
        refs.append(TemplateRef(key="journal.highlight.overrides", slots=slots))
    refs.append(TemplateRef(key=f"journal.articulation.{review.rule_articulation}"))
    return refs


def build_review(
    entries: list[JournalEntry],
    as_of: dt.date,
    renderer: Renderer,
    meta: ResponseMeta,
    policy: JournalPolicy | None = None,
) -> JournalReviewResponse:
    """Compute the user's patterns from their journal.

    Args:
        entries: Journal entries sent by the device (not stored).
        as_of: Review date; later entries are ignored.
        renderer: Renderer for the user's locale.
        meta: Response metadata.
        policy: Optional policy override.

    Returns:
        Numbers, weekly points and rendered highlights.
    """
    policy = policy or get_journal_policy()
    kept = [e for e in entries if e.date <= as_of]
    planned = [e for e in kept if e.plan is not None and e.plan.started]
    logged = [e for e in planned if e.plan_followed is not None]
    paused = [e for e in kept if e.level_shown in policy.pause_levels]
    completion = [e for e in paused if e.pause_completed is not None]
    understood = [e for e in paused if e.could_state_why is not None]
    overrides = [e for e in paused if e.overrode]
    first_rules, latest_rules, trend = rule_articulation(kept)
    review = JournalReviewResponse(
        as_of=as_of,
        total_decisions=len(kept),
        unsolicited_share_pct=percent(
            sum(e.source_type in policy.tip_sources for e in kept), len(kept)
        ),
        plans_set_pct=percent(len(planned), len(kept)),
        plans_followed_pct=percent(sum(bool(e.plan_followed) for e in logged), len(logged)),
        plans_pending=len(planned) - len(logged),
        pauses=len(paused),
        pause_completion_pct=percent(
            sum(bool(e.pause_completed) for e in completion), len(completion)
        ),
        comprehension_pct=percent(
            sum(bool(e.could_state_why) for e in understood), len(understood)
        ),
        reconsideration_pct=percent(sum(e.action in RECONSIDERED for e in paused), len(paused)),
        overrides_with_reason=sum(e.override_reason_given for e in overrides),
        overrides_without_reason=sum(not e.override_reason_given for e in overrides),
        own_rules_first=first_rules,
        own_rules_latest=latest_rules,
        rule_articulation=trend,
        weekly=weekly_points(kept, as_of, policy),
        meta=meta,
    )
    refs = _highlights(review, policy)
    highlights = [renderer.text(ref.key, **ref.slots) for ref in refs]
    return review.model_copy(update={"highlights": highlights, "speak": refs})
