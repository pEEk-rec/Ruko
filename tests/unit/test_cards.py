"""Stage 8: just-in-time cards (triggers, max 3, fading, safety-critical, filter, sources)."""

import pytest

from ruko.cards.catalog import get_catalog, resolve_fact
from ruko.cards.select import matching_cards, select_cards
from ruko.engine.engine import decide
from ruko.language.speak import build_speech_text
from ruko.language.templates import Renderer
from ruko.models.common import (
    Certainty,
    FundingSource,
    HoldingIntent,
    InterventionLevel,
    ProductClass,
    ReasonCode,
    SignalSource,
)
from ruko.models.event import DecisionEvent, Signal
from ruko.models.profile import UserProfile

R = ReasonCode
FULL_PLAN = {"reason_given": True, "horizon": "weeks", "reconsider_condition_given": True}


def signal(code: ReasonCode) -> Signal:
    return Signal(code=code, certainty=Certainty.LIKELY, source=SignalSource.LEXICON)


def event(**fields) -> DecisionEvent:
    base = {"is_financial_decision": True, "amount_inr": 40000}
    base.update(fields)
    return DecisionEvent.model_validate(base)


def profile(**fields) -> UserProfile:
    base = {"monthly_expenses_band": "25k_50k", "liquid_savings_band": "1l_3l"}
    base.update(fields)
    return UserProfile.model_validate(base)


def card_ids(ev: DecisionEvent, prof: UserProfile, **kwargs) -> list[str]:
    decision = decide(ev, prof)
    return [c.id for c in select_cards(ev, decision, prof, Renderer("en"), **kwargs).cards]


FIRST_TIME_FNO = event(product_class=ProductClass.DERIVATIVE, funding_source=FundingSource.BORROWED)
FNO_PROFILE = profile(experience={"derivative": "none"}, age_band="lt_30")
SCAM = event(
    product_class=ProductClass.SCHEME_OR_APP,
    signals=[signal(R.PAY_TO_INDIVIDUAL_ACCOUNT), signal(R.WITHDRAWAL_FEE_DEMAND),
             signal(R.GUARANTEED_RETURN_CLAIM), signal(R.AUTHORITY_CLAIM)],
)  # fmt: skip


# --- Catalog integrity --------------------------------------------------------------


def test_every_card_fact_resolves_with_a_source():
    for card in get_catalog().cards:
        for fact_id in card.facts:
            fact = resolve_fact(fact_id)
            assert fact.source.source_url.startswith("https://")
            assert fact.source.as_of


def test_unknown_fact_reference_fails_loudly():
    with pytest.raises(KeyError):
        resolve_fact("regulatory:no_such_fact")
    with pytest.raises(KeyError):
        resolve_fact("elsewhere:x")


# --- Triggers ---------------------------------------------------------------------------


def test_first_time_borrowed_derivative_gets_leverage_cards():
    assert card_ids(FIRST_TIME_FNO, FNO_PROFILE) == [
        "leverage_rupees",
        "loss_beyond_margin",
        "group_base_rate",
    ]


def test_scam_pattern_gets_safety_cards_first():
    assert card_ids(SCAM, profile()) == ["already_paid", "pay_to_individual", "no_assured_returns"]


def test_authority_claim_gets_registration_card():
    ev = event(signals=[signal(R.AUTHORITY_CLAIM), signal(R.GUARANTEED_RETURN_CLAIM)])
    assert "check_registration" in card_ids(ev, profile())


def test_intraday_cash_equity_gets_cost_card():
    ev = event(
        product_class=ProductClass.CASH_EQUITY,
        holding_intent=HoldingIntent.INTRADAY,
        funding_source=FundingSource.BORROWED,
    )
    assert "costs_intraday" in card_ids(ev, profile())


def test_frequent_derivative_trading_gets_cost_card():
    prof = profile(
        recent={"trades_this_week": "gt_20"},
        experience={"derivative": "regular"},
        seen_card_ids=["leverage_rupees", "loss_beyond_margin"],
    )
    ev = event(
        product_class=ProductClass.DERIVATIVE,
        plan=FULL_PLAN,
        amount_inr=5000,
        funding_source="borrowed",
    )
    assert card_ids(ev, prof) == ["group_base_rate", "costs_frequent_derivative"]


def test_tax_card_only_when_selling():
    selling = event(
        product_class=ProductClass.CASH_EQUITY,
        action="sell",
        funding_source=FundingSource.BORROWED,
    )
    buying = selling.model_copy(update={"action": "buy"})
    assert "capital_gains_holding_period" in card_ids(selling, profile())
    assert "capital_gains_holding_period" not in card_ids(buying, profile())


def test_leverage_card_needs_an_amount():
    ev = FIRST_TIME_FNO.model_copy(update={"amount_inr": None})
    assert "leverage_rupees" not in card_ids(ev, FNO_PROFILE)


# --- Limits, fading, levels ---------------------------------------------------------------


def test_never_more_than_three_cards():
    ev = SCAM.model_copy(
        update={"product_class": ProductClass.DERIVATIVE, "funding_source": FundingSource.BORROWED}
    )
    assert len(card_ids(ev, FNO_PROFILE)) == 3


def test_seen_cards_fade_and_the_next_one_takes_their_place():
    prof = FNO_PROFILE.model_copy(update={"seen_card_ids": ["leverage_rupees"]})
    assert card_ids(FIRST_TIME_FNO, prof) == ["loss_beyond_margin", "group_base_rate"]


def test_safety_critical_cards_are_shown_even_if_seen():
    prof = profile(seen_card_ids=["already_paid", "pay_to_individual", "no_assured_returns"])
    assert card_ids(SCAM, prof) == ["already_paid", "pay_to_individual", "no_assured_returns"]


def test_no_cards_below_the_pause_level():
    ev = event(signals=[signal(R.URGENCY_PRESSURE)])
    prof = profile()
    assert decide(ev, prof).level == InterventionLevel.L1
    assert card_ids(ev, prof) == []


def test_explicit_card_request_can_lower_the_level_threshold():
    ev = event(product_class=ProductClass.DERIVATIVE, plan=FULL_PLAN)
    prof = profile(experience={"derivative": "regular"})
    assert decide(ev, prof).level == InterventionLevel.L0
    assert card_ids(ev, prof) == []
    assert card_ids(ev, prof, min_level=InterventionLevel.L0)[0] == "leverage_rupees"


def test_matching_is_deterministic():
    decision = decide(SCAM, profile())
    first = [c.id for c in matching_cards(SCAM, decision, profile())]
    assert all([c.id for c in matching_cards(SCAM, decision, profile())] == first for _ in range(5))


# --- Content: numbers, sources, caveats ---------------------------------------------------


def test_leverage_card_uses_the_users_rupees():
    decision = decide(FIRST_TIME_FNO, FNO_PROFILE)
    card = select_cards(FIRST_TIME_FNO, decision, FNO_PROFILE, Renderer("en")).cards[0]
    assert card.id == "leverage_rupees"
    assert "₹40,000" in card.body and "10%" in card.body and "₹4,000" in card.body
    assert "not a forecast" in card.body


def test_base_rate_card_is_a_cited_group_statistic_with_caveat():
    decision = decide(FIRST_TIME_FNO, FNO_PROFILE)
    selection = select_cards(FIRST_TIME_FNO, decision, FNO_PROFILE, Renderer("en"))
    card = next(c for c in selection.cards if c.id == "group_base_rate")
    assert "88.55%" in card.body and "FY26" in card.body
    assert "under 30" in card.body
    assert "does not show cause and effect" in card.body
    assert "not a prediction for you" in card.body
    assert card.sources[0].source_url.startswith("https://www.sebi.gov.in/")
    assert not card.verified_by_human
    assert "base_rates:eds_fy26_loss_makers_age_lt_30" in selection.unverified_fact_ids


def test_tax_card_carries_its_as_of_date_and_stays_unverified():
    ev = event(
        product_class=ProductClass.MUTUAL_FUND,
        action="sell",
        funding_source=FundingSource.BORROWED,
    )
    decision = decide(ev, profile())
    selection = select_cards(ev, decision, profile(), Renderer("en"))
    card = next(c for c in selection.cards if c.id == "capital_gains_holding_period")
    assert card.as_of == "2024-07-23"
    assert "2024-07-23" in card.body and "20%" in card.body and "12.5%" in card.body
    assert "₹1,25,000" in card.body
    assert not card.verified_by_human
    assert "regulatory:capital_gains_listed_equity" in selection.unverified_fact_ids


def test_cards_without_facts_have_no_sources():
    decision = decide(SCAM, profile())
    card = select_cards(SCAM, decision, profile(), Renderer("en")).cards[0]
    assert card.id == "already_paid" and card.sources == [] and card.as_of is None


ALL_CARD_SCENARIOS = [
    (FIRST_TIME_FNO, FNO_PROFILE),
    (SCAM, profile()),
    (event(signals=[signal(R.IMPERSONATION_SUSPECTED)]), profile()),
    (
        event(product_class=ProductClass.CASH_EQUITY, holding_intent=HoldingIntent.INTRADAY,
              funding_source=FundingSource.BORROWED),
        profile(),
    ),
    (
        event(product_class=ProductClass.CASH_EQUITY, action="sell",
              funding_source=FundingSource.BORROWED),
        profile(),
    ),
    (
        event(product_class=ProductClass.DERIVATIVE, funding_source=FundingSource.BORROWED),
        profile(recent={"trades_this_week": "gt_20"}, seen_card_ids=["leverage_rupees",
                "loss_beyond_margin", "group_base_rate"]),
    ),
]  # fmt: skip


@pytest.mark.parametrize("locale", ["en", "hi", "kn"])
def test_every_card_renders_and_passes_the_filter_in_every_locale(locale):
    shown: set[str] = set()
    for ev, prof in ALL_CARD_SCENARIOS:
        renderer = Renderer(locale)
        selection = select_cards(ev, decide(ev, prof), prof, renderer)
        shown |= {c.id for c in selection.cards}
        assert renderer.blocked_count == 0
        assert renderer.missing_keys == []
        assert all(c.title and c.body for c in selection.cards)
        speech = build_speech_text(selection.speak, Renderer(locale), max_chars=10_000)
        assert speech.item_count == len(selection.speak)
    assert shown == {card.id for card in get_catalog().cards}
