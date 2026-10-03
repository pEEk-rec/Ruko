"""Stage 10: stateless journal review (patterns on fixed journals, empty/tiny, trend)."""

import datetime as dt
import inspect

import pytest

from ruko.guardrails.output_filter import find_violations
from ruko.journal import review as review_module
from ruko.journal.review import build_review, get_journal_policy, trend_direction, week_start
from ruko.language.templates import Renderer
from ruko.models.journal import JournalEntry, WeekPoint
from ruko.models.responses import ResponseMeta

AS_OF = dt.date(2026, 10, 3)  # a Saturday
_counter = iter(range(10_000))


def entry(day: dt.date, level: str = "L0", **fields) -> JournalEntry:
    base = {
        "id": f"e{next(_counter)}",
        "date": day,
        "product_class": "cash_equity",
        "source_type": "own_research",
        "level_shown": level,
        "action": "went_ahead",
        "followed_own_rules": True,
        "exit_plan_set": False,
    }
    base.update(fields)
    return JournalEntry.model_validate(base)


def review(entries, locale: str = "en", as_of: dt.date = AS_OF):
    meta = ResponseMeta(request_id="test-request", locale=locale)
    return build_review(entries, as_of, Renderer(locale), meta)


def weeks_ago(n: int, day_offset: int = 0) -> dt.date:
    return week_start(AS_OF) - dt.timedelta(weeks=n) + dt.timedelta(days=day_offset)


FIXED = [
    entry(weeks_ago(0), "L2", source_type="unsolicited_group", overrode=True,
          followed_own_rules=False, exit_plan_set=True, exit_plan_followed=False),
    entry(weeks_ago(0, 1), "L0", exit_plan_set=True, exit_plan_followed=True),
    entry(weeks_ago(1), "L3", source_type="influencer", overrode=False, exit_plan_set=True),
    entry(weeks_ago(1, 2), "L1", source_type="known_person", exit_plan_set=True,
          exit_plan_followed=True),
]  # fmt: skip


def test_patterns_on_a_fixed_journal():
    result = review(FIXED)
    assert result.total_decisions == 4
    assert result.tip_driven_pct == 50.0  # group + influencer, not known person
    assert result.rules_followed_pct == 75.0
    assert result.exit_plan_set_pct == 100.0
    assert result.exit_plan_followed_pct == pytest.approx(66.7)  # 2 of 3 logged
    assert result.exit_plans_pending == 1
    assert result.pauses == 2 and result.overrides == 1


def test_weekly_points_count_interventions_per_decision():
    points = review(FIXED).weekly
    assert [p.week_start for p in points] == [weeks_ago(1), weeks_ago(0)]
    assert [(p.decisions, p.interventions) for p in points] == [(2, 2), (2, 1)]
    assert [p.per_decision for p in points] == [1.0, 0.5]


def test_falling_trend_is_the_less_dependency_metric():
    entries = []
    for weeks, levels in ((5, "L2 L1 L2"), (4, "L1 L1 L0"), (3, "L2 L0 L0"),
                          (2, "L0 L0 L1"), (1, "L0 L0 L0"), (0, "L0 L1 L0")):  # fmt: skip
        entries += [entry(weeks_ago(weeks, i), lvl) for i, lvl in enumerate(levels.split())]
    assert review(entries).trend == "falling"


def test_rising_and_steady_trends():
    rising = [entry(weeks_ago(w), "L0" if w > 1 else "L2") for w in range(4)]
    steady = [entry(weeks_ago(w), "L1") for w in range(4)]
    assert review(rising).trend == "rising"
    assert review(steady).trend == "steady"


def test_trend_needs_enough_weeks():
    policy = get_journal_policy()
    points = [WeekPoint(week_start=weeks_ago(i), decisions=1, interventions=1, per_decision=1.0)
              for i in range(policy.min_weeks_for_trend - 1)]  # fmt: skip
    assert trend_direction(points, policy) == "not_enough_data"


def test_entries_outside_the_window_or_after_as_of_are_ignored():
    policy = get_journal_policy()
    old = entry(weeks_ago(policy.weeks_window + 2), "L3")
    future = entry(AS_OF + dt.timedelta(days=3), "L3")
    result = review([old, future, entry(AS_OF, "L0")])
    assert result.total_decisions == 2  # the old one still counts in totals, not in the trend
    assert [p.week_start for p in result.weekly] == [week_start(AS_OF)]


def test_empty_journal():
    result = review([])
    assert result.total_decisions == 0
    assert result.tip_driven_pct is None and result.exit_plan_followed_pct is None
    assert result.weekly == [] and result.trend == "not_enough_data"
    assert [ref.key for ref in result.speak] == ["journal.empty"]


def test_tiny_journal_says_it_is_too_early():
    result = review([entry(AS_OF, "L1")])
    keys = [ref.key for ref in result.speak]
    assert keys[0] == "journal.too_few"
    assert "journal.highlight.exit_followed" not in keys  # nothing logged yet
    assert keys[-1] == "journal.trend.not_enough_data"


@pytest.mark.parametrize("locale", ["en", "hi", "kn"])
def test_highlights_render_and_pass_the_filter(locale):
    result = review(FIXED, locale)
    assert len(result.highlights) == len(result.speak)
    assert all(text and not find_violations(text) for text in result.highlights)
    assert "50" in result.highlights[0]


def test_review_never_scores_ranks_or_stores():
    fields = set(review(FIXED).model_dump())
    assert not fields & {"score", "rank", "percentile", "grade", "pnl", "profit"}
    source = inspect.getsource(review_module)
    for banned in ("open(", "write", "sqlite", "httpx"):
        assert banned not in source
