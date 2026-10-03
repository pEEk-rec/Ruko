"""Stage 10 (v2): stateless journal review with the impact metrics (hand-computed results)."""

import datetime as dt
import inspect

import pytest

from ruko.guardrails.output_filter import find_violations
from ruko.journal import review as review_module
from ruko.journal.review import build_review, rule_articulation, week_start
from ruko.language.templates import Renderer
from ruko.models.journal import JournalEntry
from ruko.models.responses import ResponseMeta

AS_OF = dt.date(2026, 10, 3)
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
    }
    base.update(fields)
    return JournalEntry.model_validate(base)


def review(entries, locale: str = "en"):
    meta = ResponseMeta(request_id="test-request", locale=locale)
    return build_review(entries, AS_OF, Renderer(locale), meta)


def days_ago(n: int) -> dt.date:
    return AS_OF - dt.timedelta(days=n)


PLAN_FULL = {"reason_given": True, "horizon": "months", "reconsider_condition_given": True}

FIXED = [
    # 1: group tip, L2 pause read through, understood, user continued WITH a reason
    entry(days_ago(20), "L2", source_type="unsolicited_group", overrode=True,
          override_reason_given=True, pause_completed=True, could_state_why=True,
          own_rules_count=1),
    # 2: influencer, L3 pause skimmed, not understood, user waited (reconsidered)
    entry(days_ago(15), "L3", source_type="influencer", action="delayed",
          pause_completed=False, could_state_why=False),
    # 3: known person, L2 pause, continued WITHOUT a reason, plan written and followed
    entry(days_ago(10), "L2", source_type="known_person", overrode=True,
          pause_completed=True, plan=PLAN_FULL, plan_followed=True),
    # 4: own research, L0, plan written, result not logged yet
    entry(days_ago(2), "L0", plan={"reason_given": True}, own_rules_count=3),
]  # fmt: skip


def test_impact_metrics_on_a_fixed_journal():
    result = review(FIXED)
    assert result.total_decisions == 4
    assert result.unsolicited_share_pct == 50.0  # group + influencer of 4
    assert result.plans_set_pct == 50.0  # entries 3 and 4
    assert result.plans_followed_pct == 100.0 and result.plans_pending == 1
    assert result.pauses == 3
    assert result.pause_completion_pct == pytest.approx(66.7)  # 2 of 3
    assert result.comprehension_pct == 50.0  # 1 of 2 answered
    assert result.reconsideration_pct == pytest.approx(33.3)  # entry 2 delayed
    assert (result.overrides_with_reason, result.overrides_without_reason) == (1, 1)
    assert (result.own_rules_first, result.own_rules_latest) == (1, 3)
    assert result.rule_articulation == "growing"


def test_weekly_points_are_data_not_a_score():
    result = review(FIXED)
    assert sum(p.decisions for p in result.weekly) == 4
    assert all(0 <= p.per_decision <= 1 for p in result.weekly)
    fields = set(result.model_dump())
    assert not fields & {"score", "rank", "trend_success", "dependency_falling", "pnl"}


@pytest.mark.parametrize(
    ("counts", "trend"),
    [
        ((2, 2), "steady"),
        ((3, 1), "shrinking"),
        ((1, 4), "growing"),
        ((None, 2), "not_enough_data"),
    ],
)
def test_rule_articulation(counts, trend):
    entries = [entry(days_ago(9 - i), own_rules_count=c) for i, c in enumerate(counts)]
    assert rule_articulation(entries)[2] == trend


def test_plans_count_toward_articulation():
    entries = [entry(days_ago(5), own_rules_count=2, own_plans_count=0),
               entry(days_ago(1), own_rules_count=2, own_plans_count=2)]  # fmt: skip
    assert rule_articulation(entries)[2] == "growing"


def test_entries_after_as_of_are_ignored():
    result = review([entry(AS_OF + dt.timedelta(days=3), "L3"), entry(AS_OF)])
    assert result.total_decisions == 1
    assert [p.week_start for p in result.weekly] == [week_start(AS_OF)]


def test_empty_journal():
    result = review([])
    assert result.total_decisions == 0
    assert result.unsolicited_share_pct is None and result.pause_completion_pct is None
    assert result.weekly == [] and result.rule_articulation == "not_enough_data"
    assert [ref.key for ref in result.speak] == ["journal.empty"]


def test_tiny_journal_says_it_is_too_early():
    result = review([entry(AS_OF, "L1")])
    keys = [ref.key for ref in result.speak]
    assert keys[0] == "journal.too_few"
    assert "journal.highlight.plans_followed" not in keys
    assert "journal.highlight.overrides" not in keys
    assert keys[-1] == "journal.articulation.not_enough_data"


@pytest.mark.parametrize("locale", ["en", "hi", "kn"])
def test_highlights_render_and_pass_the_filter(locale):
    result = review(FIXED, locale)
    assert len(result.highlights) == len(result.speak)
    assert all(text and not find_violations(text) for text in result.highlights)
    assert "50" in result.highlights[0]


def test_review_never_stores_anything():
    source = inspect.getsource(review_module)
    for banned in ("open(", "write", "sqlite", "httpx"):
        assert banned not in source
