"""Stateless journal review: the user's own patterns, computed for one request.

The device sends its journal; the server returns numbers and rendered template text and
keeps nothing. Patterns:

- share of decisions that started from a group tip or an influencer
- share within the user's own rules
- exit plans written, and followed (of those logged)
- pauses (L2/L3) and how often the user continued past them
- interventions per decision, week by week, and whether that is falling: the
  "needs Ruko less over time" metric

No score, no ranking, no comparison with other people, no judgement of outcomes.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from functools import lru_cache

from ruko.data_files import load_yaml
from ruko.language.templates import Renderer
from ruko.models.common import InterventionLevel, SourceType
from ruko.models.journal import JournalEntry, JournalReviewResponse, TrendDirection, WeekPoint
from ruko.models.responses import ResponseMeta, TemplateRef

TEMPLATE_KEYS = frozenset(
    {
        "journal.empty",
        "journal.too_few",
        *(f"journal.highlight.{k}" for k in ("tip_share", "rules", "exit_plans")),
        *(f"journal.highlight.{k}" for k in ("exit_followed", "overrides")),
        *(f"journal.trend.{t}" for t in ("falling", "rising", "steady", "not_enough_data")),
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
    min_weeks_for_trend: int
    trend_threshold: float
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
        min_weeks_for_trend=int(raw["min_weeks_for_trend"]),
        trend_threshold=float(raw["trend_threshold"]),
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


def trend_direction(points: list[WeekPoint], policy: JournalPolicy) -> TrendDirection:
    """Compare the average of the earlier half of weeks with the later half."""
    if len(points) < policy.min_weeks_for_trend:
        return "not_enough_data"
    half = len(points) // 2
    earlier = [p.per_decision for p in points[:half]]
    later = [p.per_decision for p in points[-half:]]
    change = sum(later) / len(later) - sum(earlier) / len(earlier)
    if change <= -policy.trend_threshold:
        return "falling"
    if change >= policy.trend_threshold:
        return "rising"
    return "steady"


def _fmt(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".")


def _highlights(review: JournalReviewResponse, policy: JournalPolicy) -> list[TemplateRef]:
    if review.total_decisions == 0:
        return [TemplateRef(key="journal.empty")]
    refs: list[TemplateRef] = []
    if review.total_decisions < policy.min_entries_for_patterns:
        refs.append(TemplateRef(key="journal.too_few"))
    for key, value in (
        ("journal.highlight.tip_share", review.tip_driven_pct),
        ("journal.highlight.rules", review.rules_followed_pct),
        ("journal.highlight.exit_plans", review.exit_plan_set_pct),
        ("journal.highlight.exit_followed", review.exit_plan_followed_pct),
    ):
        if value is not None:
            refs.append(TemplateRef(key=key, slots={"pct": _fmt(value)}))
    if review.pauses:
        slots = {"count": str(review.overrides), "total": str(review.pauses)}
        refs.append(TemplateRef(key="journal.highlight.overrides", slots=slots))
    refs.append(TemplateRef(key=f"journal.trend.{review.trend}"))
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
        Numbers, a weekly trend and rendered highlights.
    """
    policy = policy or get_journal_policy()
    kept = [e for e in entries if e.date <= as_of]
    total = len(kept)
    logged_plans = [e for e in kept if e.exit_plan_set and e.exit_plan_followed is not None]
    paused = [e for e in kept if e.level_shown in policy.pause_levels]
    points = weekly_points(kept, as_of, policy)
    review = JournalReviewResponse(
        as_of=as_of,
        total_decisions=total,
        tip_driven_pct=percent(sum(e.source_type in policy.tip_sources for e in kept), total),
        rules_followed_pct=percent(sum(e.followed_own_rules for e in kept), total),
        exit_plan_set_pct=percent(sum(e.exit_plan_set for e in kept), total),
        exit_plan_followed_pct=percent(
            sum(bool(e.exit_plan_followed) for e in logged_plans), len(logged_plans)
        ),
        exit_plans_pending=sum(e.exit_plan_set and e.exit_plan_followed is None for e in kept),
        pauses=len(paused),
        overrides=sum(e.overrode for e in paused),
        weekly=points,
        trend=trend_direction(points, policy),
        meta=meta,
    )
    refs = _highlights(review, policy)
    highlights = [renderer.text(ref.key, **ref.slots) for ref in refs]
    return review.model_copy(update={"highlights": highlights, "speak": refs})
