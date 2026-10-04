"""Stage 4: the deterministic safety engine."""

import re
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from ruko.engine.attention import apply_attention_budget
from ruko.engine.base_rates import format_percent, select_base_rate
from ruko.engine.decay import apply_decay
from ruko.engine.engine import decide
from ruko.engine.exposure import Quantity, compute_numbers, months_of_expenses, share_of_savings_pct
from ruko.engine.levels import compute_level, compute_levels
from ruko.engine.plan import match_plan
from ruko.engine.policy import get_intervention_policy, render_doc_tables
from ruko.models.common import (
    CONTENT_CODES,
    Certainty,
    FundingSource,
    HoldingIntent,
    InterventionLevel,
    PaymentDestination,
    ProductClass,
    ReasonCode,
    Severity,
    SignalSource,
    SourceType,
)
from ruko.models.decision import Reason
from ruko.models.event import DecisionEvent, DecisionPlan, Signal
from ruko.models.profile import AttentionCounts, PlannedDecision, UserProfile

POLICY = get_intervention_policy()
L0, L1, L2, L3 = (InterventionLevel.L0, InterventionLevel.L1, InterventionLevel.L2,
                  InterventionLevel.L3)  # fmt: skip
HIGH_CONTENT = frozenset(c for c in CONTENT_CODES if POLICY.severity(c) == Severity.HIGH)
ROOT = Path(__file__).resolve().parents[2]


def event(**kw) -> DecisionEvent:
    base = {"is_financial_decision": True, "product_class": "cash_equity", "amount_inr": 5000,
            "funding_source": "savings", "source_type": "own_research"}  # fmt: skip
    base.update(kw)
    return DecisionEvent(**base)


def profile(**kw) -> UserProfile:
    base = {"monthly_expenses_band": "25k_50k", "liquid_savings_band": "1l_3l"}
    base.update(kw)
    return UserProfile(**base)


def sig(code: ReasonCode, certainty: Certainty = Certainty.LIKELY) -> Signal:
    return Signal(code=code, certainty=certainty, source=SignalSource.LEXICON)


def codes_of(decision) -> set[ReasonCode]:
    return set(decision.reason_codes)


# ------------------------------------------------------------------ metrics


def test_months_and_share_with_exact_numbers():
    expenses = Quantity(40000, 40000, 40000, True)
    savings = Quantity(200000, 200000, 200000, True)
    m = months_of_expenses(80000, expenses)
    assert (m.low, m.high, m.typical) == (2.0, 2.0, 2.0)
    s = share_of_savings_pct(50000, savings)
    assert (s.low, s.high, s.typical) == (25.0, 25.0, 25.0)


def test_band_numbers_are_ranges_with_typical():
    numbers = compute_numbers(event(amount_inr=75000), profile(), POLICY)
    assert numbers.basis == "band"
    m = numbers.months_of_expenses  # 25k-50k band, typical 37.5k
    assert (m.low, m.typical, m.high) == (1.5, 2.0, 3.0)
    s = numbers.share_of_savings_pct  # 1L-3L band, typical 2L
    assert (s.low, s.typical, s.high) == (25.0, 37.5, 75.0)
    r = numbers.remaining_savings_inr
    assert (r.low, r.typical, r.high) == (25000, 125000, 225000)


def test_zero_savings_gives_no_share_and_a_shortfall():
    numbers = compute_numbers(event(amount_inr=10000), profile(liquid_savings_inr=0), POLICY)
    assert numbers.share_of_savings_pct is None
    assert numbers.remaining_savings_inr.typical == -10000


def test_adverse_moves_only_for_leveraged_products_and_labelled():
    lev = compute_numbers(event(product_class="derivative", amount_inr=40000), profile(), POLICY)
    assert [(m.move_pct, m.loss_inr) for m in lev.adverse_moves] == [
        (10.0, 4000), (25.0, 10000), (50.0, 20000)]  # fmt: skip
    assert all(m.label == "illustration" for m in lev.adverse_moves)
    assert compute_numbers(event(amount_inr=40000), profile(), POLICY).adverse_moves == []


def test_no_amount_no_numbers():
    numbers = compute_numbers(event(amount_inr=None), profile(), POLICY)
    assert numbers.amount_inr is None and numbers.months_of_expenses is None


# ------------------------------------------------------------------ rules and boundaries


@pytest.mark.parametrize(("limit", "breach"), [(25, False), (24, True)])
def test_max_share_boundary_exact(limit, breach):
    p = profile(liquid_savings_inr=200000, rules={"max_share_of_savings_pct": limit})
    d = decide(event(amount_inr=50000), p)  # exactly 25%
    assert (ReasonCode.RULE_MAX_SHARE_EXCEEDED in codes_of(d)) is breach


def test_max_share_certainty_reflects_band():
    rules = {"max_share_of_savings_pct": 30}
    d = decide(event(amount_inr=75000), profile(rules=rules))  # typical 37.5%, low 25%
    reason = next(r for r in d.reasons if r.code == ReasonCode.RULE_MAX_SHARE_EXCEEDED)
    assert reason.certainty == Certainty.POSSIBLE
    rules = {"max_share_of_savings_pct": 20}
    d = decide(event(amount_inr=75000), profile(rules=rules))  # breach even at low (25%)
    reason = next(r for r in d.reasons if r.code == ReasonCode.RULE_MAX_SHARE_EXCEEDED)
    assert reason.certainty == Certainty.LIKELY


@pytest.mark.parametrize(("amount", "breach"), [(10000, False), (10001, True)])
def test_max_amount_boundary(amount, breach):
    d = decide(event(amount_inr=amount), profile(rules={"max_amount_inr": 10000}))
    assert (ReasonCode.RULE_MAX_AMOUNT_EXCEEDED in codes_of(d)) is breach


@pytest.mark.parametrize(
    ("funding", "code", "level"),
    [
        (FundingSource.BORROWED, ReasonCode.BORROWED_FUNDS, L2),
        (FundingSource.EMERGENCY_FUND, ReasonCode.EMERGENCY_FUNDS, L2),
        (FundingSource.PROTECTED_GOAL, ReasonCode.PROTECTED_GOAL_FUNDS, L3),
    ],
)
def test_funding_sources(funding, code, level):
    d = decide(event(funding_source=funding), profile())
    assert code in codes_of(d)
    assert d.level == level


@pytest.mark.parametrize(("target", "breach"), [(4, False), (5, True)])
def test_emergency_buffer_boundary(target, breach):
    # exact: expenses 40k, savings 200k, amount 40k -> 160k left = 4.0 months
    p = profile(monthly_expenses_inr=40000, liquid_savings_inr=200000,
                emergency_buffer_months=target)  # fmt: skip
    d = decide(event(amount_inr=40000), p)
    assert (ReasonCode.EMERGENCY_FUNDS in codes_of(d)) is breach


# ------------------------------------------------------------------ the level table (v2)

PLAN = DecisionPlan(reason_given=True, horizon="months", reconsider_condition_given=True)
R = ReasonCode


def test_routine_decision_is_silent():
    d = decide(event(), profile())
    assert d.level == L0 and d.reasons == []
    assert d.dimension_levels.content == L0 and d.dimension_levels.behavioural == L0


def test_unsolicited_small_within_rules_is_l1():
    d = decide(event(source_type=SourceType.UNSOLICITED_GROUP), profile())
    assert d.level == L1
    assert codes_of(d) == {R.UNSOLICITED_SOURCE}
    assert d.content_codes == [R.UNSOLICITED_SOURCE] and d.behavioural_codes == []


def test_first_time_leveraged_borrowed_is_l2_with_exposure():
    p = profile(experience={"derivative": "none"})
    d = decide(event(product_class="derivative", amount_inr=40000, funding_source="borrowed",
                     plan=PLAN), p)  # fmt: skip
    assert d.level == L2
    assert {R.FIRST_TIME_PRODUCT, R.LEVERAGED_PRODUCT, R.BORROWED_FUNDS} <= codes_of(d)
    assert d.exposure.adverse_moves
    assert {"first_time_leveraged", "borrowed_or_emergency_funds"} <= set(d.matched_rules)
    assert d.dimension_levels.behavioural == L2 and d.dimension_levels.content == L0


def test_experienced_leveraged_with_plan_inside_rules_is_silent():
    p = profile(experience={"derivative": "regular"})
    d = decide(event(product_class="derivative", plan=PLAN), p)
    assert d.level == L0
    assert codes_of(d) == {R.LEVERAGED_PRODUCT}


def test_no_plan_on_a_risky_product_is_a_mild_nudge():
    d = decide(event(product_class="crypto"), profile())
    assert d.level == L1
    assert d.reasons[0].code == R.UNPLANNED_DECISION
    assert d.reasons[0].certainty == Certainty.POSSIBLE


def test_incomplete_plan_is_a_mild_nudge_and_complete_plan_is_quiet():
    partial = DecisionPlan(reason_given=True)
    d = decide(event(product_class="crypto", plan=partial), profile())
    assert codes_of(d) == {R.PLAN_INCOMPLETE} and d.level == L1
    assert decide(event(product_class="crypto", plan=PLAN), profile()).level == L0
    follows = DecisionPlan(matches_prior_plan=True)
    assert decide(event(product_class="crypto", plan=follows), profile()).level == L0


def test_plan_not_expected_for_mutual_funds():
    assert decide(event(product_class="mutual_fund"), profile()).level == L0


def test_multiple_rule_breaches_is_l3():
    p = profile(rules={"max_amount_inr": 1000})
    d = decide(event(funding_source="borrowed"), p)
    assert d.level == L3 and "multiple_rule_breaches" in d.matched_rules
    assert d.cooling_off_minutes == POLICY.l3_default_cooling_off_minutes
    assert not d.recovery_entry  # a behavioural L3 is not a fraud pattern


@pytest.mark.parametrize("code", sorted(HIGH_CONTENT))
def test_high_content_signals_are_l3_with_recovery(code):
    d = decide(
        event(is_financial_decision=False, signals=[sig(code, Certainty.POSSIBLE)]), profile()
    )
    assert d.level == L3 and d.dimension_levels.content == L3
    assert d.recovery_entry


def test_payment_destination_field_raises_pay_to_individual():
    d = decide(event(payment_destination=PaymentDestination.INDIVIDUAL_ACCOUNT), profile())
    assert R.PAY_TO_INDIVIDUAL_ACCOUNT in codes_of(d)
    assert d.level == L3


@pytest.mark.parametrize(
    ("codes", "level"),
    [
        ([R.URGENCY_PRESSURE], L1),
        ([R.URGENCY_PRESSURE, R.UNSOLICITED_SOURCE], L1),
        ([R.AUTHORITY_CLAIM], L1),
        ([R.AUTHORITY_CLAIM, R.GUARANTEED_RETURN_CLAIM], L2),
        ([R.AUTHORITY_CLAIM, R.GUARANTEED_RETURN_CLAIM, R.URGENCY_PRESSURE], L2),
        ([R.AUTHORITY_CLAIM, R.GUARANTEED_RETURN_CLAIM, R.APP_INSTALL_REQUEST], L3),
    ],
)
def test_content_signal_tiers_and_counts(codes, level):
    d = decide(event(signals=[sig(c) for c in codes]), profile())
    assert d.level == level and d.dimension_levels.content == level


def test_medium_content_with_a_behavioural_trigger_is_l2():
    p = profile(experience={"ipo": "none"})
    d = decide(event(product_class="ipo", signals=[sig(R.GUARANTEED_RETURN_CLAIM)]), p)
    assert d.level == L2 and "medium_content_with_trigger" in d.matched_rules
    assert d.dimension_levels.content == L1 and d.dimension_levels.behavioural == L1


def test_not_a_financial_decision_ignores_personal_rules():
    p = profile(rules={"max_amount_inr": 10}, recent={"post_loss": True})
    d = decide(event(is_financial_decision=False), p)
    assert d.level == L0 and d.base_rate is None


def test_declared_context_is_a_mild_nudge():
    d = decide(event(), profile(recent={"post_loss": True, "trades_this_week": "gt_20"}))
    assert {R.POST_LOSS_REENTRY_DECLARED, R.HIGH_FREQUENCY_DECLARED} <= codes_of(d)
    assert d.level == L1
    lev = decide(event(product_class="derivative", plan=PLAN),
                 profile(recent={"post_loss": True}))  # fmt: skip
    assert lev.level == L1


def test_duplicate_codes_keep_strongest_certainty_and_sort_by_severity():
    signals = [sig(R.UNSOLICITED_SOURCE, Certainty.UNCLEAR), sig(R.UNSOLICITED_SOURCE)]
    d = decide(event(signals=signals, funding_source="borrowed"), profile())
    assert [r.code for r in d.reasons] == [R.BORROWED_FUNDS, R.UNSOLICITED_SOURCE]
    assert d.reasons[1].certainty == Certainty.LIKELY


# ------------------------------------------------------------------ plans


def _plan(**kw) -> PlannedDecision:
    base = {
        "id": "p1",
        "product_class": "derivative",
        "amount_min_inr": 1000,
        "amount_max_inr": 10000,
        "horizon": "weeks",
        "reconsider_condition_given": True,
    }
    base.update(kw)
    return PlannedDecision(**base)  # fmt: skip


def test_planned_decision_gets_relief():
    p = profile(experience={"derivative": "none"}, plans=[_plan()])
    d = decide(event(product_class="derivative", amount_inr=5000), p)
    assert d.matched_plan_id == "p1"
    assert not codes_of(d) & {R.FIRST_TIME_PRODUCT, R.UNPLANNED_DECISION, R.PLAN_INCOMPLETE}
    assert d.level == L0


@pytest.mark.parametrize(("amount", "deviation"), [(10000, False), (10001, True)])
def test_plan_deviation_boundary(amount, deviation):
    d = decide(event(product_class="derivative", amount_inr=amount),
               profile(plans=[_plan()]))  # fmt: skip
    assert (R.PLAN_DEVIATION in codes_of(d)) is deviation
    assert R.UNPLANNED_DECISION not in codes_of(d)


def test_named_plan_mismatch_is_deviation():
    m = match_plan(event(product_class="ipo", plan_id="p1"), [_plan()])
    assert m.plan is None and m.deviation


# ------------------------------------------------------------------ attention and decay


def _low_reason() -> Reason:
    return Reason(code=R.UNSOLICITED_SOURCE, severity=Severity.LOW,
                  certainty=Certainty.LIKELY, source=SignalSource.RULE)  # fmt: skip


@pytest.mark.parametrize(("used", "suppressed"), [(2, False), (3, True)])
def test_attention_budget_boundary(used, suppressed):
    level, state = apply_attention_budget(L1, [_low_reason()], AttentionCounts(l1_this_week=used),
                                          POLICY)  # fmt: skip
    assert state.suppressed_by_budget is suppressed
    assert level == (L0 if suppressed else L1)


def test_budget_never_suppresses_medium_l1_or_l2_l3():
    exhausted = profile(attention={"l1_this_week": 99})
    medium = decide(event(), profile(recent={"post_loss": True}, attention={"l1_this_week": 99}))
    assert medium.level == L1
    assert decide(event(funding_source="borrowed"), exhausted).level == L2
    scam = decide(event(signals=[sig(R.WITHDRAWAL_FEE_DEMAND)]), exhausted)
    assert scam.level == L3


@pytest.mark.parametrize(("streak", "decayed"), [(4, False), (5, True)])
def test_decay_boundary(streak, decayed):
    level, applied = apply_decay(L1, {R.FIRST_TIME_PRODUCT}, streak, POLICY)
    assert applied is decayed
    assert level == (L0 if decayed else L1)


def test_decay_only_for_novelty_only_nudges_and_never_content():
    assert apply_decay(L1, {R.FIRST_TIME_PRODUCT, R.UNSOLICITED_SOURCE}, 50, POLICY) == (L1, False)
    assert apply_decay(L1, {R.FIRST_TIME_PRODUCT, R.UNPLANNED_DECISION}, 50, POLICY) == (L1, False)
    p = profile(experience={"ipo": "none"}, attention={"rule_following_streak": 9})
    d = decide(event(product_class="ipo"), p)
    assert d.computed_level == L1 and d.level == L0 and d.decay_applied


def test_cooling_off_uses_users_rule_at_l2():
    d = decide(event(funding_source="borrowed"), profile(rules={"cooling_off_minutes": 60}))
    assert d.level == L2 and d.cooling_off_minutes == 60
    assert decide(event(source_type="unsolicited_group"), profile()).cooling_off_minutes is None


# ------------------------------------------------------------------ base rates


@pytest.mark.usefixtures("unverified_facts")
def test_base_rate_prefers_age_band_and_is_unverified():
    d = decide(event(product_class="derivative", plan=PLAN), profile(age_band="lt_30"))
    assert d.base_rate.fact_id == "eds_fy26_loss_makers_age_lt_30"
    assert d.base_rate.slots == {"pct": "88.55", "year": "FY26"}
    assert d.base_rate.source.verified_by_human is False
    assert d.base_rate.caveat_key == "base_rate.caveat_descriptive"
    assert "sebi.gov.in" in d.base_rate.source.source_url


def test_base_rate_overall_and_intraday_and_none():
    overall = select_base_rate(event(product_class="derivative"), profile())
    assert overall.fact_id == "eds_fy26_loss_makers_all"
    intraday = select_base_rate(event(holding_intent=HoldingIntent.INTRADAY), profile())
    assert intraday.fact_id == "intraday_fy23_loss_makers_all"
    assert intraday.caveat_key == "base_rate.caveat_group"
    assert select_base_rate(event(product_class="mutual_fund"), profile()) is None


def test_format_percent():
    assert [format_percent(v) for v in (87.7, 87.80, 71.0, 88.55)] == [
        "87.7",
        "87.8",
        "71",
        "88.55",
    ]


# ------------------------------------------------------------------ properties

codes_st = st.sets(st.sampled_from(list(ReasonCode)))


@given(codes_st, codes_st)
def test_adding_reasons_never_lowers_the_level(a, b):
    assert compute_level(a | b, POLICY).rank >= compute_level(a, POLICY).rank


events_st = st.builds(
    DecisionEvent,
    is_financial_decision=st.booleans(),
    product_class=st.sampled_from(list(ProductClass)),
    amount_inr=st.one_of(st.none(), st.integers(1, 10**8)),
    funding_source=st.sampled_from(list(FundingSource)),
    source_type=st.sampled_from(list(SourceType)),
    payment_destination=st.sampled_from(list(PaymentDestination)),
    holding_intent=st.sampled_from(list(HoldingIntent)),
    plan=st.one_of(st.none(), st.builds(
        DecisionPlan, reason_given=st.booleans(),
        horizon=st.one_of(st.none(), st.sampled_from(["days", "years", "unsure"])),
        reconsider_condition_given=st.booleans(),
        matches_prior_plan=st.one_of(st.none(), st.booleans()))),
    signals=st.lists(st.builds(Signal, code=st.sampled_from(list(ReasonCode)),
                               certainty=st.sampled_from(list(Certainty)),
                               source=st.just(SignalSource.LEXICON)), max_size=5),
)  # fmt: skip
profiles_st = st.builds(
    UserProfile,
    monthly_expenses_band=st.sampled_from([None, "lt_10k", "25k_50k", "gt_2l"]),
    liquid_savings_band=st.sampled_from([None, "lt_25k", "1l_3l", "gt_25l"]),
    emergency_buffer_months=st.one_of(st.none(), st.integers(0, 12)),
    rules=st.fixed_dictionaries({
        "max_share_of_savings_pct": st.one_of(st.none(), st.integers(1, 100)),
        "max_amount_inr": st.one_of(st.none(), st.integers(1, 10**7)),
        "cooling_off_minutes": st.one_of(st.none(), st.integers(0, 120)),
    }),
    experience=st.dictionaries(st.sampled_from(list(ProductClass)),
                               st.sampled_from(["none", "some", "regular"])),
    recent=st.fixed_dictionaries({
        "post_loss": st.booleans(),
        "trades_this_week": st.sampled_from(["0", "1_5", "6_20", "gt_20"]),
    }),
    attention=st.fixed_dictionaries({"l1_this_week": st.integers(0, 10),
                                     "rule_following_streak": st.integers(0, 20)}),
)  # fmt: skip


@settings(max_examples=400, deadline=None)
@given(events_st, profiles_st)
def test_engine_invariants(ev, prof):
    d = decide(ev, prof)
    codes = codes_of(d)
    assert d.override_allowed is True
    if codes & HIGH_CONTENT:
        assert d.level == L3 and d.recovery_entry
    if d.level == L0:
        assert all(r.severity == Severity.LOW for r in d.reasons)
    assert d.level.rank <= d.computed_level.rank
    if d.level != d.computed_level:
        assert d.computed_level == L1  # budget and decay touch L1 only
    if d.decay_applied:
        assert not d.content_codes
    both = max(d.dimension_levels.content.rank, d.dimension_levels.behavioural.rank)
    assert both <= d.computed_level.rank
    assert decide(ev, prof) == d


@given(st.sampled_from(sorted(c for c in CONTENT_CODES if POLICY.severity(c) == Severity.LOW)))
def test_a_single_low_signal_alone_never_exceeds_l1(code):
    assert compute_level({code}, POLICY).rank <= L1.rank


@given(codes_st)
def test_dimension_levels_use_only_their_own_codes(codes):
    result = compute_levels(codes, POLICY)
    content_only = compute_levels({c for c in codes if c in CONTENT_CODES}, POLICY)
    assert result.content == content_only.content


@settings(max_examples=200, deadline=None)
@given(events_st, profiles_st, st.sampled_from(list(ReasonCode)))
def test_adding_a_signal_never_lowers_the_computed_level(ev, prof, extra):
    before = decide(ev, prof).computed_level
    after = decide(ev.model_copy(update={"signals": [*ev.signals, sig(extra)]}), prof)
    assert after.computed_level.rank >= before.rank


# ------------------------------------------------------------------ docs stay in sync


def _between(text: str, marker: str) -> str:
    match = re.search(rf"<!-- {marker}:start -->\n(.*?)\n<!-- {marker}:end -->", text, re.S)
    assert match, marker
    return match.group(1)


def test_policy_doc_matches_yaml():
    doc = (ROOT / "docs" / "intervention_policy.md").read_text(encoding="utf-8")
    tables = render_doc_tables(POLICY)
    assert _between(doc, "codes-table") == tables["codes"]
    assert _between(doc, "rules-table") == tables["rules"]
    assert _between(doc, "params-table") == tables["params"]


def test_reason_codes_doc_matches_yaml():
    doc = (ROOT / "docs" / "reason_codes.md").read_text(encoding="utf-8")
    rows = re.findall(
        r"^\| `([A-Z_]+)` \|[^|]*\| (content|behavioural) \| (low|medium|high) \|[^|]*\|"
        r" `([a-z_.]+)` \|$",
        doc,
        re.M,
    )
    assert {r[0] for r in rows} == {c.value for c in ReasonCode}
    for code, dimension, severity, template_key in rows:
        expected = "content" if ReasonCode(code) in CONTENT_CODES else "behavioural"
        assert dimension == expected, code
        assert severity == POLICY.severity(ReasonCode(code)).value, code
        assert template_key == f"reason.{code.lower()}"
