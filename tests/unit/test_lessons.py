"""Decision-specific lessons (triggers, caps, fading, validator, speech)."""

import base64

import pytest

from ruko.cards.catalog import get_catalog, resolve_fact
from ruko.engine.engine import decide
from ruko.language.speak import build_speech_text
from ruko.language.templates import Renderer, get_template_store
from ruko.learn.catalog import get_lesson_catalog
from ruko.learn.select import (
    LessonContext,
    explain_calculation,
    explain_decision,
    matching_lessons,
    plan_explanations,
    render_lesson,
    speak_refs_for_lesson,
)
from ruko.models.calculation import CalculationInputs
from ruko.models.common import (
    Action,
    CalculatorTool,
    Certainty,
    DecisionStage,
    FundingSource,
    InterventionLevel,
    ProductClass,
    ReasonCode,
    SignalSource,
)
from ruko.models.event import DecisionEvent, Signal
from ruko.models.profile import UserProfile
from tests.helpers import PROFILE, analyze_body, make_client
from tests.unit.test_cards import FNO_PROFILE, SCAM, event, profile

R = ReasonCode
LOCALES = ("en", "hi", "kn")


def lesson_ids(ev: DecisionEvent, prof: UserProfile, **kwargs) -> list[str]:
    decision = decide(ev, prof)
    result = explain_decision(ev, decision, prof, Renderer("en"), **kwargs)
    return [lesson.id for lesson in result.lessons]


def ctx(**fields) -> LessonContext:
    return LessonContext(**fields)


# --- Catalog integrity ----------------


def test_every_lesson_fact_resolves_with_a_source_and_date():
    for lesson in get_lesson_catalog().lessons:
        assert lesson.facts or lesson.own_guidance, f"{lesson.id} cites nothing"
        for fact_id in lesson.facts:
            fact = resolve_fact(fact_id)
            assert fact.source.source_url.startswith("https://")
            assert fact.source.as_of


def test_every_lesson_has_text_in_every_locale_with_matching_slots():
    store = get_template_store()
    for lesson in get_lesson_catalog().lessons:
        for key in lesson.template_keys():
            slots = {loc: store.get(loc, key).slots for loc in LOCALES}
            assert len(set(slots.values())) == 1, key
            assert all(store.get(loc, key).response_type == "lesson" for loc in LOCALES)


def test_lesson_bodies_are_micro_lessons_of_60_to_120_words():
    store = get_template_store()
    for lesson in get_lesson_catalog().lessons:
        for key in (lesson.body_key, *([lesson.body_amount_key] if lesson.amount_slot else [])):
            words = len(store.get("en", key).text.split())
            assert 60 <= words <= 120, f"{key}: {words} words"


def test_no_lesson_is_marked_verified_before_a_human_checked_it():
    assert not any(lesson.verified_by_human for lesson in get_lesson_catalog().lessons)


def test_catalog_limits_match_the_plan():
    catalog = get_lesson_catalog()
    assert (catalog.max_lessons, catalog.max_explanation_items) == (2, 3)


# --- All lessons pass the output validator in every locale ----------------


@pytest.mark.parametrize("locale", LOCALES)
def test_every_lesson_renders_cleanly_in_every_locale(locale):
    renderer = Renderer(locale)
    for spec in get_lesson_catalog().lessons:
        for amount in (None, 25000):
            rendered, _ = render_lesson(spec, renderer, amount)
            assert rendered.title and rendered.body
            assert rendered.read_seconds > 0
            assert rendered.sources or spec.own_guidance, spec.id
    assert renderer.blocked_count == 0
    assert renderer.missing_keys == []


def test_lessons_never_assert_outcomes_or_recommend():
    for spec in get_lesson_catalog().lessons:
        body = render_lesson(spec, Renderer("en"), 25000)[0].body.lower()
        for phrase in ("you will get", "you will earn", "expected return", "is safe", "legit"):
            assert phrase not in body, (spec.id, phrase)
        for word in ("should buy", "should sell", "best fund", "recommend"):
            assert word not in body, (spec.id, word)


# --- Triggers ----------------


def test_withdrawal_fee_demand_triggers_the_never_pay_lesson():
    found = matching_lessons(ctx(reason_codes=frozenset({R.WITHDRAWAL_FEE_DEMAND})), UserProfile())
    assert [lesson.id for lesson in found] == ["never_pay_to_withdraw"]


def test_guaranteed_return_claim_triggers_its_lesson():
    found = matching_lessons(
        ctx(reason_codes=frozenset({R.GUARANTEED_RETURN_CLAIM})), UserProfile()
    )
    assert [lesson.id for lesson in found] == ["guaranteed_returns"]


def test_authority_claim_triggers_registration_lesson():
    found = matching_lessons(ctx(reason_codes=frozenset({R.AUTHORITY_CLAIM})), UserProfile())
    assert [lesson.id for lesson in found] == ["check_registration"]


def test_derivative_triggers_leverage_lesson():
    found = matching_lessons(ctx(product_class=ProductClass.DERIVATIVE), UserProfile())
    assert [lesson.id for lesson in found] == ["leverage_basics"]


def test_ipo_triggers_ipo_lesson():
    found = matching_lessons(ctx(product_class=ProductClass.IPO), UserProfile())
    assert [lesson.id for lesson in found] == ["ipo_basics"]


def test_selling_equity_triggers_tax_lesson_but_buying_does_not():
    sell = ctx(action=Action.SELL, product_class=ProductClass.CASH_EQUITY)
    buy = ctx(action=Action.BUY, product_class=ProductClass.CASH_EQUITY)
    assert [lesson.id for lesson in matching_lessons(sell, UserProfile())] == ["selling_costs_tax"]
    assert matching_lessons(buy, UserProfile()) == []
    intraday_free = ctx(action=Action.SELL, product_class=ProductClass.SCHEME_OR_APP)
    assert matching_lessons(intraday_free, UserProfile()) == []


def test_sip_and_goal_calculations_trigger_the_sip_lesson():
    for tool in (CalculatorTool.SIP, CalculatorTool.GOAL):
        found = matching_lessons(ctx(calc_tool=tool), UserProfile())
        assert [lesson.id for lesson in found] == ["sip_adds_up"]
    assert matching_lessons(ctx(calc_tool=CalculatorTool.INFLATION), UserProfile()) == []


def test_leveraged_consequence_calculation_triggers_leverage_lesson():
    inputs = CalculationInputs(tool=CalculatorTool.CONSEQUENCE, amount_inr=40000, leverage=5)
    plain = CalculationInputs(tool=CalculatorTool.CONSEQUENCE, amount_inr=40000)
    assert [x.id for x in explain_calculation(inputs, UserProfile(), Renderer("en")).lessons] == [
        "leverage_basics"
    ]
    assert explain_calculation(plain, UserProfile(), Renderer("en")).lessons == []


def test_ordinary_decision_gets_no_lessons():
    assert lesson_ids(event(product_class=ProductClass.CASH_EQUITY), profile()) == []


# --- Levels ----------------


def test_lessons_follow_the_card_rule_and_wait_for_l2_on_a_pause():
    ev = event(
        product_class=ProductClass.DERIVATIVE,
        funding_source=FundingSource.SAVINGS,
        signals=[Signal(code=R.LEVERAGED_PRODUCT, certainty=Certainty.LIKELY,
                        source=SignalSource.LEXICON)],
    )  # fmt: skip
    prof = profile(experience={"derivative": "some"})
    decision = decide(ev, prof)
    result = explain_decision(ev, decision, prof, Renderer("en"))
    assert (decision.level.rank >= InterventionLevel.L2.rank) == bool(result.lessons)
    forced = explain_decision(
        ev, decision, prof, Renderer("en"), lesson_min_level=InterventionLevel.L0
    )
    assert [x.id for x in forced.lessons] == ["leverage_basics"]


# --- The shared cap: at most 2 lessons, at most 3 explanation items ----------------


def test_scam_decision_keeps_cards_plus_lessons_within_three():
    prof = profile()
    decision = decide(SCAM, prof)
    result = explain_decision(SCAM, decision, prof, Renderer("en"))
    assert len(result.lessons) <= 2
    assert len(result.cards.cards) + len(result.lessons) <= 3
    assert result.lessons, "a scam-pattern decision should get a safety lesson"


def test_a_chosen_lesson_replaces_its_related_card():
    cards = {c.id: c for c in get_catalog().cards}
    lessons = {x.id: x for x in get_lesson_catalog().lessons}
    kept_cards, kept_lessons = plan_explanations(
        [cards["no_assured_returns"]], [lessons["guaranteed_returns"]]
    )
    assert kept_cards == []
    assert [x.id for x in kept_lessons] == ["guaranteed_returns"]


def test_a_lesson_still_replaces_a_higher_priority_card_it_is_about():
    cards = {c.id: c for c in get_catalog().cards}
    lessons = {x.id: x for x in get_lesson_catalog().lessons}
    # loss_beyond_margin (60) outranks nothing here, but the leverage lesson (70) is about it
    kept_cards, kept_lessons = plan_explanations(
        [cards["leverage_rupees"], cards["loss_beyond_margin"]], [lessons["leverage_basics"]]
    )
    assert [c.id for c in kept_cards] == ["leverage_rupees"]
    assert [x.id for x in kept_lessons] == ["leverage_basics"]


def test_plan_fits_everything_into_three_and_prefers_safety_critical_items():
    cards = list(get_catalog().cards)
    lessons = list(get_lesson_catalog().lessons)
    kept_cards, kept_lessons = plan_explanations(cards, lessons)
    assert len(kept_cards) + len(kept_lessons) == 3
    assert len(kept_lessons) <= 2
    assert all(c.safety_critical for c in kept_cards)
    assert all(x.safety_critical for x in kept_lessons)


def test_plan_keeps_a_non_critical_lesson_when_nothing_critical_competes():
    lessons = {x.id: x for x in get_lesson_catalog().lessons}
    cards = {c.id: c for c in get_catalog().cards}
    kept_cards, kept_lessons = plan_explanations(
        [cards["group_base_rate"], cards["costs_intraday"], cards["capital_gains_holding_period"]],
        [lessons["selling_costs_tax"]],
    )
    assert len(kept_cards) + len(kept_lessons) == 3
    assert [x.id for x in kept_lessons] == ["selling_costs_tax"]
    assert "capital_gains_holding_period" not in [c.id for c in kept_cards]


def test_at_most_two_lessons_even_when_more_match():
    everything = ctx(
        stage=DecisionStage.CONSIDER_ACTION,
        product_class=ProductClass.DERIVATIVE,
        action=Action.SELL,
        reason_codes=frozenset(
            {R.WITHDRAWAL_FEE_DEMAND, R.GUARANTEED_RETURN_CLAIM, R.AUTHORITY_CLAIM,
             R.LEVERAGED_PRODUCT}
        ),
    )  # fmt: skip
    found = matching_lessons(everything, UserProfile())
    assert len(found) == 2
    assert all(lesson.safety_critical for lesson in found)  # critical ones come first
    assert [x.id for x in found] == ["never_pay_to_withdraw", "guaranteed_returns"]


# --- Fading and the safety-critical override -------------------------------------------------


def test_seen_lessons_fade():
    context = ctx(product_class=ProductClass.IPO)
    assert matching_lessons(context, UserProfile())
    seen = UserProfile(seen_lesson_ids=["ipo_basics"])
    assert matching_lessons(context, seen) == []


def test_safety_critical_lessons_never_fade():
    context = ctx(reason_codes=frozenset({R.GUARANTEED_RETURN_CLAIM}))
    seen = UserProfile(seen_lesson_ids=["guaranteed_returns"])
    assert [x.id for x in matching_lessons(context, seen)] == ["guaranteed_returns"]


# --- Production hides unverified lessons ----------------


def test_production_hides_every_unverified_lesson():
    context = ctx(
        product_class=ProductClass.DERIVATIVE,
        reason_codes=frozenset({R.GUARANTEED_RETURN_CLAIM}),
    )
    assert matching_lessons(context, UserProfile(), show_unverified=True)
    assert matching_lessons(context, UserProfile(), show_unverified=False) == []


@pytest.mark.usefixtures("unverified_facts")
def test_lesson_reports_unverified_facts_it_cites():
    rendered, unverified = render_lesson(
        get_lesson_catalog().get("guaranteed_returns"), Renderer("en")
    )
    assert not rendered.verified_by_human
    assert set(unverified) == {"investor_pages:spot_any_scam", "regulatory:ia_no_assured_returns"}


# --- The user's own numbers ----------------


def test_amount_lessons_use_the_users_rupees():
    spec = get_lesson_catalog().get("sip_adds_up")
    with_amount, _ = render_lesson(spec, Renderer("en"), 5000)
    without, _ = render_lesson(spec, Renderer("en"), None)
    assert "₹5,000" in with_amount.body
    assert "₹" not in without.body


def test_selling_lesson_months_come_from_the_cited_fact():
    spec = get_lesson_catalog().get("selling_costs_tax")
    assert "12 months" in render_lesson(spec, Renderer("en"))[0].body


# --- Speech by lesson id ----------------


def test_speak_refs_for_a_lesson_are_its_own_templates():
    refs = speak_refs_for_lesson("guaranteed_returns")
    assert [r.key for r in refs] == [
        "lesson.guaranteed_returns.title",
        "lesson.guaranteed_returns.body",
    ]
    text = build_speech_text(refs, Renderer("en"), 2500).text
    assert "assured or near-certain returns" in text


def test_speak_refs_unknown_lesson_raises():
    with pytest.raises(KeyError):
        speak_refs_for_lesson("buy_this_stock")


def test_speak_refs_hidden_lesson_raises_in_production():
    with pytest.raises(KeyError):
        speak_refs_for_lesson("guaranteed_returns", show_unverified=False)


# --- API ----------------


SCAM_TEXT = (
    "Guaranteed 3x return in 7 days. Pay 18% GST to withdraw your profits. "
    "Join our Telegram group, act today!"
)


def test_pause_response_carries_lessons_within_the_cap():
    client = make_client()
    body = analyze_body(SCAM_TEXT, answers={"amount_inr": 20000, "funding_source": "emergency_fund",
                        "product_class": "scheme_or_app"}, profile=PROFILE)  # fmt: skip
    data = client.post("/v1/analyze", json=body).json()
    assert data["kind"] == "pause"
    assert data["lessons"], data
    assert len(data["lessons"]) <= 2
    assert len(data["cards"]) + len(data["lessons"]) <= 3
    for lesson in data["lessons"]:
        assert lesson["title"] and lesson["body"] and lesson["sources"]
        assert lesson["speak"] and lesson["verified_by_human"] is False


def test_content_report_carries_only_safety_critical_lessons():
    client = make_client()
    data = client.post(
        "/v1/analyze", json=analyze_body("Is this message real? " + SCAM_TEXT)
    ).json()
    assert data["kind"] == "content_report"
    assert data["lessons"]
    assert all(lesson["safety_critical"] for lesson in data["lessons"])


def test_calculation_response_carries_the_sip_lesson_with_the_users_amount():
    client = make_client()
    data = client.post(
        "/v1/analyze",
        json=analyze_body("What will my SIP of 5000 a month look like over 10 years?"),
    ).json()
    assert data["kind"] == "calculation", data
    assert [x["id"] for x in data["lessons"]] == ["sip_adds_up"]
    assert "₹5,000" in data["lessons"][0]["body"]
    assert data["lessons"][0]["related_tool"] == "sip"


def test_seen_lesson_ids_in_the_profile_fade_a_lesson():
    client = make_client()
    body = analyze_body("What will my SIP of 5000 a month look like over 10 years?",
                        profile={**PROFILE, "seen_lesson_ids": ["sip_adds_up"]})  # fmt: skip
    assert client.post("/v1/analyze", json=body).json()["lessons"] == []


def test_production_hides_unverified_lessons_in_responses():
    client = make_client(environment="prod")
    data = client.post(
        "/v1/analyze",
        json=analyze_body("What will my SIP of 5000 a month look like over 10 years?"),
    ).json()
    assert data["kind"] == "calculation"
    assert data["lessons"] == []


def test_speak_a_lesson_by_id():
    from ruko.providers.speech.fake import FakeSpeechProvider

    fake = FakeSpeechProvider()
    client = make_client(speech=[fake])
    response = client.post("/v1/speak", json={"locale": "en", "lesson_id": "guaranteed_returns"})
    data = response.json()
    assert data["kind"] == "speech"
    assert base64.b64decode(data["audio_base64"]).startswith(b"RIFF")
    assert "near-certain returns" in fake.spoken[0][1]


def test_speak_a_lesson_in_hindi_reads_hindi():
    from ruko.providers.speech.fake import FakeSpeechProvider

    fake = FakeSpeechProvider()
    client = make_client(speech=[fake])
    client.post("/v1/speak", json={"locale": "hi", "lesson_id": "ipo_basics"})
    assert "आवेदन" in fake.spoken[0][1]


def test_speak_rejects_unknown_lesson_and_ambiguous_requests():
    client = make_client()
    for body in (
        {"locale": "en", "lesson_id": "nope"},
        {"locale": "en"},
        {"locale": "en", "lesson_id": "ipo_basics", "items": [{"key": "pause.override"}]},
        {"locale": "en", "lesson_id": "Bad Id!"},
    ):
        response = client.post("/v1/speak", json=body)
        assert response.status_code in (400, 422), (body, response.text)


def test_fno_first_time_pause_gets_leverage_lesson_in_place_of_its_card():
    prof = FNO_PROFILE
    ev = event(product_class=ProductClass.DERIVATIVE, funding_source=FundingSource.BORROWED)
    decision = decide(ev, prof)
    result = explain_decision(ev, decision, prof, Renderer("en"))
    assert [x.id for x in result.lessons] == ["leverage_basics"]
    assert "loss_beyond_margin" not in [c.id for c in result.cards.cards]
    assert len(result.cards.cards) + len(result.lessons) <= 3


def test_own_guidance_lessons_make_no_factual_claim_so_they_carry_no_numbers():
    store = get_template_store()
    own = [lesson for lesson in get_lesson_catalog().lessons if lesson.own_guidance]
    assert own, "the catalog is expected to have some general-guidance lessons"
    for lesson in own:
        for locale in LOCALES:
            text = store.get(locale, lesson.body_key).text
            assert not any(ch.isdigit() for ch in text), (lesson.id, locale)
        rendered, _ = render_lesson(lesson, Renderer("en"))
        assert rendered.own_guidance and not rendered.sources
