"""Phase 2 P1: calculator arithmetic, input parsing and scenario selection."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from ruko.models.common import CalculatorTool
from ruko.tools import finance
from ruko.tools.calculate import (
    get_calculator_policy,
    merge_inputs,
    missing_fields,
    pct,
    scenario_values,
)
from ruko.tools.params import choose_tool, read_inputs, read_numbers

# --- Hand-computed values ---------------------------------------------------------------


def test_sip_matches_hand_computed_annuity_due():
    # 5000 a month for 120 months at 12% a year (1% a month), contributions at month start:
    # 5000 * ((1.01^120 - 1) / 0.01) * 1.01 = 11,61,695 (rounded)
    zero, twelve = finance.sip_illustration(5000, 120, [0, 12])
    assert zero.value_inr == zero.invested_inr == 600_000
    assert twelve.invested_inr == 600_000
    assert twelve.value_inr == 1_161_695
    assert twelve.gain_inr == 561_695


def test_sip_series_has_a_point_per_year_and_the_end():
    (result,) = finance.sip_illustration(1000, 30, [6])
    assert [p.month for p in result.series] == [0, 12, 24, 30]
    assert result.series[0].value_inr == 0
    assert result.series[-1].value_inr == result.value_inr


def test_sip_edge_cases():
    assert finance.sip_value(5000, 0, 12) == 0
    assert finance.sip_value(5000, 1, 0) == 5000
    assert finance.sip_value(1, 600, 30) > 0  # large horizon and rate do not overflow
    with pytest.raises(ValueError):
        finance.sip_value(5000, -1, 6)


def test_goal_contribution_rounds_up_to_reach_the_goal():
    zero, twelve = finance.goal_contribution(500_000, 36, [0, 12])
    assert zero.monthly_needed_inr == 13_889  # ceil(500000 / 36)
    assert twelve.monthly_needed_inr == 11_493  # 500000 / 43.5076 = 11492.3 -> 11493
    assert finance.sip_value(twelve.monthly_needed_inr, 36, 12) >= 500_000


def test_goal_already_reached_needs_nothing():
    (result,) = finance.goal_contribution(100_000, 12, [6], already_saved_inr=200_000)
    assert result.monthly_needed_inr == 0
    with pytest.raises(ValueError):
        finance.goal_contribution(100_000, 0, [6])


def test_inflation_future_cost_and_today_value():
    (result,) = finance.inflation_purchasing_power(100_000, 10, [6])
    assert result.future_cost_inr == 179_085  # 100000 * 1.06^10
    assert result.today_value_inr == 55_839  # 100000 / 1.06^10
    (none,) = finance.inflation_purchasing_power(100_000, 0, [6])
    assert none.future_cost_inr == none.today_value_inr == 100_000


def test_consequence_without_and_with_leverage():
    plain = finance.consequence(40_000, [25])
    assert plain[0].loss_inr == 10_000 and plain[0].left_inr == 30_000
    assert not plain[0].exceeds_amount
    levered = finance.consequence(50_000, [10, 25], leverage=5)
    assert levered[0].exposure_inr == 250_000
    assert levered[1].loss_inr == 62_500 and levered[1].left_inr == -12_500
    assert levered[1].exceeds_amount
    with pytest.raises(ValueError):
        finance.consequence(1000, [10], leverage=0.5)


def test_cost_illustration():
    fixed, pct_based = finance.cost_illustration(
        10_000, 20, 12, [finance.CostAssumption(20, 0), finance.CostAssumption(0, 0.5)]
    )
    assert fixed.trades == 240 and fixed.total_cost_inr == 4_800
    assert pct_based.per_trade_cost_inr == 50 and pct_based.total_cost_inr == 12_000


# --- Properties -------------------------------------------------------------------------

amounts = st.integers(min_value=1, max_value=1_000_000)
months = st.integers(min_value=0, max_value=600)
rates = st.floats(min_value=0, max_value=30, allow_nan=False)


@given(amounts, months, rates)
def test_more_months_never_reduce_sip_value(monthly, n, rate):
    assert finance.sip_value(monthly, n + 1, rate) >= finance.sip_value(monthly, n, rate)


@given(amounts, st.integers(min_value=1, max_value=600), rates, rates)
def test_a_higher_rate_never_reduces_sip_value(monthly, n, a, b):
    low, high = sorted((a, b))
    assert finance.sip_value(monthly, n, high) >= finance.sip_value(monthly, n, low)


@given(amounts, st.floats(min_value=1, max_value=100), st.floats(min_value=1, max_value=100),
       st.floats(min_value=1, max_value=50))  # fmt: skip
def test_a_larger_fall_never_gives_a_better_outcome(amount, a, b, leverage):
    small, large = sorted((a, b))
    first, second = finance.consequence(amount, [small, large], leverage)
    assert second.left_inr <= first.left_inr


@given(amounts, st.integers(min_value=1, max_value=600), rates, rates)
def test_a_higher_rate_never_needs_more_each_month(goal, n, a, b):
    low, high = sorted((a, b))
    at_low, at_high = finance.goal_contribution(goal, n, [low, high])
    assert at_high.monthly_needed_inr <= at_low.monthly_needed_inr


# --- Scenario selection -----------------------------------------------------------------


def test_example_rates_fill_in_and_user_rates_are_kept():
    policy = get_calculator_policy()
    examples = policy.example_rates[CalculatorTool.SIP]
    bounds = policy.bounds["rate_pct"]
    assert scenario_values([], examples, bounds, policy) == ([0.0, 6.0, 12.0], True)
    chosen, used_example = scenario_values([15], examples, bounds, policy)
    assert 15 in chosen and len(chosen) >= 2 and used_example
    assert len(scenario_values([1, 2, 3, 4, 5], examples, bounds, policy)[0]) == 4
    assert 99 not in scenario_values([99], examples, bounds, policy)[0]  # out of bounds


def test_pct_format():
    assert pct(6.0) == "6" and pct(0.5) == "0.5" and pct(12.25) == "12.25"


# --- Parsing the user's words -----------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "tool", "expected"),
    [
        ("What will my SIP of 5000 a month look like?", "sip", {"monthly_inr": 5000}),
        ("If I invest 10000 a month for 10 years at 12% what do I get?", "sip",
         {"monthly_inr": 10_000, "months": 120, "rates_pct": [12.0]}),
        ("What happens to 40000 if this falls 25%?", "consequence",
         {"amount_inr": 40_000, "drops_pct": [25.0]}),
        ("I put 50k in options with 5x leverage, what if it drops 20%", "consequence",
         {"amount_inr": 50_000, "drops_pct": [20.0], "leverage": 5.0}),
        ("How much should I save every month for my goal of 5 lakh in 3 years?", "goal",
         {"goal_inr": 500_000, "months": 36}),
        ("What will 1 lakh be worth in 10 years with 6% inflation?", "inflation",
         {"amount_inr": 100_000, "years": 10, "rates_pct": [6.0]}),
        ("brokerage on 20 trades a month of Rs 10,000 each", "costs",
         {"trade_value_inr": 10_000, "trades_per_month": 20}),
        ("मेरी 5000 की एसआईपी 10 साल में कितनी होगी?", "sip", {"monthly_inr": 5000, "months": 120}),
        ("हर महीने 5000 एसआईपी 10 साल", "sip", {"monthly_inr": 5000, "months": 120}),
        ("ತಿಂಗಳಿಗೆ 5000 ಎಸ್‌ಐಪಿ 10 ವರ್ಷದಲ್ಲಿ ಎಷ್ಟಾಗುತ್ತದೆ?", "sip", {"monthly_inr": 5000, "months": 120}),
        ("40,000 ಶೇಕಡಾ 25 ಕುಸಿದರೆ ಏನಾಗುತ್ತದೆ", "consequence",
         {"amount_inr": 40_000, "drops_pct": [25.0]}),
        ("₹2,50,000 goal in 24 months", "goal", {"goal_inr": 250_000, "months": 24}),
    ],
)  # fmt: skip
def test_tool_and_inputs_are_read_from_the_users_words(text, tool, expected):
    assert choose_tool(text) == CalculatorTool(tool)
    inputs = read_inputs(text, CalculatorTool(tool))
    for name, value in expected.items():
        assert getattr(inputs, name) == value, name


def test_small_bare_numbers_are_not_rupees():
    numbers = read_numbers("buy 1 lot of 2 options")
    assert numbers.amounts == [] and numbers.monthly == []


def test_no_tool_when_unclear():
    assert choose_tool("calculate something for me") is None


# --- Merging and missing inputs ---------------------------------------------------------


def test_answers_win_over_words_and_llm_only_fills_gaps():
    from ruko.models.calculation import CalculationInputs

    answered = CalculationInputs(months=60)
    from_text = CalculationInputs(tool=CalculatorTool.SIP, monthly_inr=5000, months=120)
    from_llm = CalculationInputs(tool=CalculatorTool.GOAL, monthly_inr=1, rates_pct=[9])
    merged = merge_inputs(answered, from_text, from_llm)
    assert merged.months == 60 and merged.monthly_inr == 5000
    assert merged.tool == CalculatorTool.SIP and merged.rates_pct == [9]


def test_missing_fields_per_tool():
    from ruko.models.calculation import CalculationInputs

    assert missing_fields(CalculationInputs()) == ["calculation.tool"]
    assert missing_fields(CalculationInputs(tool=CalculatorTool.TAX)) == ["calculation.tool"]
    assert missing_fields(CalculationInputs(tool=CalculatorTool.SIP, monthly_inr=10)) == [
        "calculation.months"
    ]
    assert missing_fields(CalculationInputs(tool=CalculatorTool.CONSEQUENCE, amount_inr=5)) == []


def test_trades_per_month_can_be_said_as_times_a_month():
    from ruko.tools.params import choose_tool, read_inputs

    text = "How much will I pay in charges if I trade 50000 worth 10 times a month?"
    inputs = read_inputs(text, choose_tool(text))
    assert (inputs.trade_value_inr, inputs.trades_per_month) == (50000, 10)
    assert stage_of(text) == "calculate"


def stage_of(text: str) -> str:
    from ruko.understanding.stage import classify_stage

    return classify_stage(text).stage.value
