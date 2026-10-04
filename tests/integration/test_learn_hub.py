"""The Learn list: always available, ordered for the person, with tappable terms."""

import pytest

from ruko.language.templates import Renderer
from ruko.learn.catalog import get_lesson_catalog
from ruko.learn.terms import find_terms
from tests.helpers import PROFILE, analyze_body, make_client


def learn(client, profile=None, locale="en"):
    return client.post("/v1/learn", json={"locale": locale, "profile": profile or {}}).json()


def lesson(client, lesson_id, profile=None, locale="en"):
    body = {"locale": locale, "lesson_id": lesson_id, "profile": profile or {}}
    return client.post("/v1/learn/lesson", json=body).json()


def analyze(client, text, **extra):
    return client.post("/v1/analyze", json=analyze_body(text, **extra)).json()


# --- the list needs no trigger and no message ---


def test_the_learn_list_shows_every_lesson_under_a_topic_with_no_trigger():
    hub = learn(make_client())
    assert hub["kind"] == "learn_hub"
    listed = [item["id"] for group in hub["topics"] for item in group["lessons"]]
    assert sorted(listed) == sorted(item.id for item in get_lesson_catalog().lessons)
    assert hub["total"] == len(listed) and hub["read_count"] == 0
    assert all(item["summary"] for group in hub["topics"] for item in group["lessons"])


def test_a_newcomer_starts_at_the_beginning_of_the_default_path():
    assert learn(make_client())["featured"]["id"] == get_lesson_catalog().path[0]


def test_what_was_read_fades_from_featured_and_counts_as_progress():
    first = get_lesson_catalog().path[0]
    hub = learn(make_client(), {"seen_lesson_ids": [first]})
    assert hub["featured"]["id"] != first and hub["read_count"] == 1
    flat = {i["id"]: i for g in hub["topics"] for i in g["lessons"]}
    assert flat[first]["seen"] is True


def test_when_everything_is_read_nothing_is_featured_but_the_list_stays():
    every = [lesson_.id for lesson_ in get_lesson_catalog().lessons]
    hub = learn(make_client(), {"seen_lesson_ids": every})
    assert hub["featured"] is None and hub["read_count"] == hub["total"]


# --- adapting to the person ---


def test_a_recent_loss_moves_the_decision_plan_lesson_to_the_front():
    hub = learn(make_client(), {"recent": {"post_loss": True}})
    assert hub["featured"]["id"] == "decision_plan"


def test_a_late_night_check_does_the_same():
    hub = learn(make_client(), {"recent": {"late_night": True}})
    assert hub["featured"]["id"] == "decision_plan"


def test_frequent_trading_does_the_same():
    hub = learn(make_client(), {"recent": {"trades_this_week": "gt_20"}})
    assert hub["featured"]["id"] == "decision_plan"


def test_someone_regular_at_shares_does_not_start_with_the_beginners_lesson():
    hub = learn(make_client(), {"experience": {"cash_equity": "regular"}})
    assert hub["featured"]["id"] != "shares_basics"
    plain = learn(make_client())
    assert plain["featured"]["id"] == "risk_and_return"


def test_someone_who_uses_derivatives_is_pointed_to_leverage_before_the_basics():
    hub = learn(make_client(), {"experience": {"derivative": "some"}})
    assert hub["featured"]["id"] == "leverage_basics"


# --- opening a lesson ---


def test_a_lesson_comes_whole_with_tappable_terms_and_a_next_one():
    data = lesson(make_client(), "mutual_funds_basics")
    assert data["kind"] == "lesson"
    body = data["lesson"]
    assert body["summary"] and "\n\n" in body["body"]
    hits = {t["id"]: t for t in data["terms"]}
    assert {"mutual_fund", "nav"} <= set(hits)
    for hit in hits.values():
        assert hit["match"] in body["body"] and hit["brief"] and hit["title"]
    assert data["next"] is not None and data["next"]["id"] != "mutual_funds_basics"


def test_the_next_lesson_follows_the_reading_path():
    assert lesson(make_client(), "sip_adds_up")["next"]["id"] == "compounding_time"


def test_an_unknown_lesson_is_a_clean_error():
    response = make_client().post(
        "/v1/learn/lesson", json={"locale": "en", "lesson_id": "nope", "profile": {}}
    )
    assert response.status_code == 422


def test_general_guidance_is_labelled_and_cites_no_source():
    data = lesson(make_client(), "decision_plan")["lesson"]
    assert data["own_guidance"] is True and data["sources"] == []
    assert lesson(make_client(), "risk_and_return")["lesson"]["own_guidance"] is False


# --- the same words in every language ---


@pytest.mark.parametrize("locale", ["hi", "kn"])
def test_lessons_and_terms_come_back_in_the_chosen_language(locale):
    data = lesson(make_client(), "mutual_funds_basics", locale=locale)
    assert data["meta"]["missing_template_keys"] == []
    assert data["terms"], "the tappable words are found in this language too"


# --- terms inside every other Ruko text ---


def test_a_glossary_answer_makes_its_other_terms_tappable_but_not_itself():
    data = analyze(make_client(), "What is a mutual fund?")
    ids = {t["id"] for t in data["terms"]}
    assert data["term"] == "mutual_fund" and "nav" in ids and "mutual_fund" not in ids


def test_the_hub_lists_every_term_with_a_short_explanation():
    hub = learn(make_client())
    assert len(hub["words"]) >= 20 and all(w["brief"] and w["title"] for w in hub["words"])


def test_terms_are_found_once_each_in_reading_order_and_capped():
    text = "SIP, NAV, margin, SEBI, demat, KYC, volatility, inflation and SIP again"
    hits = find_terms(text, Renderer("en"))
    assert len(hits) == 6
    assert [text.index(h.match) for h in hits] == sorted(text.index(h.match) for h in hits)
    assert len({h.id for h in hits}) == len(hits)


# --- a lesson is offered even when no trigger fires ---


def test_a_glossary_answer_offers_the_lesson_that_goes_deeper():
    data = analyze(make_client(), "What is an IPO?")
    assert data["learn_next"]["id"] == "ipo_basics"


def test_a_read_lesson_is_not_offered_again():
    data = analyze(make_client(), "What is an IPO?", profile={"seen_lesson_ids": ["ipo_basics"]})
    assert data["learn_next"] is None or data["learn_next"]["id"] != "ipo_basics"


def test_a_quiet_pause_still_offers_one_lesson_worth_reading():
    answers = {"amount_inr": 500, "funding_source": "savings", "product_class": "mutual_fund"}
    data = analyze(make_client(), "Thinking of a small SIP", answers=answers, profile=PROFILE)
    assert data["kind"] == "pause" and data["level"] in ("L0", "L1")
    assert data["lessons"] == [] and data["learn_next"] is not None


def test_a_strong_pause_does_not_add_a_suggestion_on_top_of_its_cards():
    tip = "Guaranteed 3x return in 7 days. Join our Telegram group, act today!"
    answers = {
        "amount_inr": 20000,
        "funding_source": "emergency_fund",
        "product_class": "scheme_or_app",
    }
    data = analyze(make_client(), tip, answers=answers, profile=PROFILE)
    assert data["level"] in ("L2", "L3") and data["learn_next"] is None


def test_a_calculation_offers_a_lesson_after_the_sip_one_was_read():
    body = {
        "locale": "en",
        "inputs": {"tool": "sip", "monthly_inr": 5000, "months": 120},
        "profile": {"seen_lesson_ids": ["sip_adds_up"]},
    }
    data = make_client().post("/v1/calculate", json=body).json()
    assert data["kind"] == "calculation" and data["lessons"] == []
    assert data["learn_next"]["id"] == "compounding_time"


# --- one word layer for the whole app ---


def test_every_kind_of_result_carries_the_same_kind_of_word_layer():
    client = make_client()
    tip = "Guaranteed 3x return in 7 days. Join our Telegram group, act today!"
    answers = {
        "amount_inr": 20000,
        "funding_source": "emergency_fund",
        "product_class": "derivative",
    }
    pause = analyze(client, tip, answers=answers, profile=PROFILE)
    assert pause["kind"] == "pause" and pause["terms"], "a pause explains its own words"
    calc = client.post(
        "/v1/calculate",
        json={"locale": "en", "inputs": {"tool": "sip", "monthly_inr": 5000, "months": 120}},
    ).json()
    assert {t["id"] for t in calc["terms"]} & {"sip", "compounding", "inflation"}
    gloss = analyze(client, "What is an IPO?")
    assert gloss["terms"] and all(t["id"] != "ipo" for t in gloss["terms"])


def test_the_word_layer_never_reads_the_users_own_words():
    text = "Guaranteed returns on this SIP margin demat KYC SEBI nominee, act today!"
    data = analyze(
        make_client(),
        text,
        answers={"amount_inr": 5000, "funding_source": "savings", "product_class": "scheme_or_app"},
        profile=PROFILE,
    )
    spoken = " ".join([data["headline"], *data["numbers_text"], *data["rules_text"]])
    for hit in data["terms"]:
        assert (
            hit["match"].lower() in spoken.lower()
            or any(
                hit["match"].lower() in (card["body"] + card["title"]).lower()
                for card in data["cards"] + data["lessons"]
            )
            or any(hit["match"].lower() in s["text"].lower() for s in data["signals"])
        ), hit


def test_a_wording_that_differs_between_texts_is_listed_once_per_wording():
    from ruko.learn.terms import lexicon

    hits = lexicon(["A SIP helps", "Your SIPs add up"], Renderer("en"))
    assert sorted(h.match for h in hits if h.id == "sip") == ["SIP", "SIPs"]


def test_chip_rows_are_not_reading_text_so_they_add_no_words():
    data = analyze(make_client(), "What is a Bollinger band?")
    assert data["related"]
    assert {t["id"] for t in data["terms"]} <= {"sebi"}, "only words in the sentence, not the chips"


def test_in_production_nothing_unchecked_is_shown_and_the_list_is_simply_empty():
    client = make_client(show_unverified_facts=False)
    hub = learn(client)
    assert hub["kind"] == "learn_hub" and hub["total"] == 0 and hub["featured"] is None
    assert hub["topics"] == [] and hub["words"], (
        "the word pop-ups are curated definitions, still shown"
    )
    response = client.post(
        "/v1/learn/lesson", json={"locale": "en", "lesson_id": "risk_and_return", "profile": {}}
    )
    assert response.status_code == 422


@pytest.mark.parametrize("locale", ["en", "hi", "kn"])
def test_texts_that_travel_inside_other_screens_never_trip_that_screens_final_check(locale):
    """Word pop-ups and lesson titles/summaries appear inside pauses, calculations, lessons and
    glossary answers, so each must pass every one of those screens' final rules."""
    from ruko.cards.glossary import get_glossary
    from ruko.guardrails.output_validator import type_violations

    kinds = ("pause", "content_report", "calculation", "glossary", "lesson", "refusal", "learn_hub")
    renderer = Renderer(locale)
    keys = [k for t in get_glossary().terms for k in (t.title_key, t.brief_key)]
    keys += [k for l_ in get_lesson_catalog().lessons for k in (l_.title_key, l_.summary_key)]
    for key in keys:
        text = renderer.text(key)
        assert not [k for k in kinds if type_violations(text, k)], (locale, key, text)


@pytest.mark.parametrize("locale", ["en", "hi", "kn"])
def test_every_lesson_opens_in_every_language(locale):
    client = make_client()
    for spec in get_lesson_catalog().lessons:
        response = client.post(
            "/v1/learn/lesson", json={"locale": locale, "lesson_id": spec.id, "profile": {}}
        )
        assert response.status_code == 200, (locale, spec.id, response.text[:200])
