"""The adaptive API: quotes, hints, visible amounts, glossary chips, the live calculator."""

import json
import logging

import pytest

from ruko.cards.glossary import MAX_RELATED, build_glossary, find_term, get_glossary
from ruko.language.templates import Renderer
from tests.helpers import PROFILE, analyze_body, make_client

TIP = "Guaranteed 3x return in 7 days. Join our Telegram group, act today!"
ANSWERS = {
    "amount_inr": 20000,
    "funding_source": "emergency_fund",
    "product_class": "scheme_or_app",
}


def analyze(client, text, **extra):
    return client.post("/v1/analyze", json=analyze_body(text, **extra)).json()


# --- E: quotes ---


def test_a_pause_quotes_the_users_own_words_behind_each_signal():
    pause = analyze(make_client(), TIP, answers=ANSWERS, profile=PROFILE)
    quotes = {s["code"]: s["quote"] for s in pause["signals"] if s["quote"]}
    assert quotes["GUARANTEED_RETURN_CLAIM"] == "Guaranteed 3x return in 7 days."
    assert all(q in TIP for q in quotes.values())


def test_behavioural_signals_have_no_quote_because_they_come_from_the_user_not_the_message():
    pause = analyze(make_client(), TIP, answers=ANSWERS, profile=PROFILE)
    by_code = {s["code"]: s for s in pause["signals"]}
    assert by_code["EMERGENCY_FUNDS"]["quote"] is None


def test_a_content_report_quotes_too():
    report = analyze(make_client(), "Is this message real? " + TIP)
    assert report["kind"] == "content_report"
    assert any(s["quote"] for s in report["signals"])


def test_contact_details_never_come_back_even_inside_a_quote():
    text = TIP + " Send the fee to rahul9876543210@ybl now"
    pause = analyze(make_client(), text, answers=ANSWERS, profile=PROFILE)
    assert "9876543210" not in json.dumps(pause)


def test_a_quote_is_never_logged_and_appears_only_in_the_quote_field(caplog):
    sentinel = "ZEBRAQUARTZ"
    text = f"{sentinel} Guaranteed 5% daily returns, join today"
    with caplog.at_level(logging.DEBUG):
        pause = analyze(make_client(), text, answers=ANSWERS, profile=PROFILE)
    assert sentinel not in caplog.text
    pause_copy = json.loads(json.dumps(pause))
    for signal in pause_copy["signals"]:
        signal["quote"] = None
    assert sentinel not in json.dumps(pause_copy)


def test_quote_text_is_not_judged_as_ruko_wording():
    """The user's own pitch may say 'buy now'; it is quoted, not asserted by Ruko."""
    text = "BANKNIFTY CE target 450. BUY NOW guaranteed profit, act today!"
    response = make_client().post("/v1/analyze", json=analyze_body(text, answers=ANSWERS))
    assert response.status_code == 200


def test_a_voice_or_unknown_message_still_works_without_quotes():
    pause = analyze(make_client(), "Join now, only today! offer ends soon", answers=ANSWERS)
    assert pause["kind"] == "pause"


# --- B: hints on the questions ---


def questions(client, text, **extra):
    data = analyze(client, text, **extra)
    assert data["kind"] == "clarify", data
    return {q["field"]: q for q in data["questions"]}


def test_the_amount_question_offers_the_amounts_the_message_mentions():
    q = questions(
        make_client(),
        "Buy now for a quick profit, deposit 5000 or 10,000 today",
        answers={"stage": "consider_action"},
    )
    hints = q["amount_inr"]["hints"]
    assert {h["value"] for h in hints} == {"5000", "10000"}
    assert all("₹" in h["label"] for h in hints)


def test_no_hint_when_the_message_mentions_no_amount():
    q = questions(
        make_client(), "Thinking of investing in this scheme", answers={"stage": "consider_action"}
    )
    assert q["amount_inr"]["hints"] == []


def test_an_amount_is_never_applied_without_the_user_confirming_it():
    client = make_client()
    data = analyze(
        client, "Deposit 5000 today for a quick profit", answers={"stage": "consider_action"}
    )
    assert data["kind"] == "clarify" and "amount_inr" in {q["field"] for q in data["questions"]}


def test_the_product_that_matches_the_message_is_tagged_not_chosen():
    q = questions(
        make_client(),
        "Join now, only today! offer ends soon, guaranteed returns",
        answers={"stage": "consider_action"},
    )
    product = q["product_class"]
    assert product["suggested"] == "scheme_or_app"
    assert product["suggested_tag"]
    assert len(product["options"]) == 7  # all choices still offered


def test_no_tag_when_the_message_gives_no_such_signal():
    q = questions(
        make_client(), "Thinking of investing something", answers={"stage": "consider_action"}
    )
    assert q["product_class"]["suggested"] is None


def test_hints_are_localised():
    q = questions(
        make_client(),
        "जल्दी करें 5000 रुपये भेजें, पक्का मुनाफा",
        locale="hi",
        answers={"stage": "consider_action"},
    )
    assert any("5,000" in h["label"] for h in q["amount_inr"]["hints"])


# --- C: the amount is visible on every path ---


def test_a_small_nudge_now_shows_the_amount_and_its_share_of_savings():
    answers = {"amount_inr": 3000, "funding_source": "savings", "product_class": "cash_equity"}
    pause = analyze(
        make_client(),
        "Join now, only today! offer ends soon. Thinking of joining",
        answers=answers,
        profile=PROFILE,
    )
    assert pause["level"] == "L1"
    assert any("₹3,000" in line for line in pause["numbers_text"])
    assert not any("months of your expenses" in line for line in pause["numbers_text"])


def test_a_quiet_l0_stays_quiet():
    answers = {"amount_inr": 2000, "funding_source": "savings", "product_class": "cash_equity"}
    pause = analyze(
        make_client(), "Thinking of buying some Infosys shares", answers=answers, profile=PROFILE
    )
    assert pause["level"] == "L0" and pause["numbers_text"] == []


def test_a_high_severity_message_is_not_held_behind_questions_and_can_be_refined_after():
    client = make_client()
    first = analyze(client, TIP + " Pay 5000 to rahul9876543210@ybl", profile=PROFILE)
    assert first["kind"] == "pause" and first["decision"]["exposure"]["amount_inr"] is None
    refined = analyze(
        client,
        TIP + " Pay 5000 to rahul9876543210@ybl",
        profile=PROFILE,
        answers={"amount_inr": 5000, "funding_source": "savings"},
    )
    assert refined["kind"] == "pause"
    assert refined["decision"]["exposure"]["amount_inr"] == 5000
    assert any("₹5,000" in line for line in refined["numbers_text"])


# --- F: glossary follow-ups ---


@pytest.mark.parametrize("locale", ["en", "hi", "kn"])
def test_every_glossary_title_finds_its_own_term_so_a_chip_tap_works(locale):
    renderer = Renderer(locale)
    glossary = get_glossary()
    for term in glossary.terms:
        title = renderer.text(term.title_key)
        found = find_term(title, glossary)
        assert found is not None and found.id == term.id, (locale, term.id, title)


def test_an_unknown_term_offers_known_terms_as_a_follow_up_up_to_the_cap():
    data = analyze(make_client(), "What is a Bollinger band?")
    known = {term.id for term in get_glossary().terms}
    assert data["kind"] == "glossary" and data["found"] is False
    assert len(data["related"]) == MAX_RELATED and {c["id"] for c in data["related"]} <= known


def test_a_found_term_offers_the_other_terms_not_itself():
    data = analyze(make_client(), "What is an IPO?")
    ids = [chip["id"] for chip in data["related"]]
    assert data["term"] == "ipo" and "ipo" not in ids and len(ids) == MAX_RELATED
    assert ids[0] == "asba"  # the same subject comes first
    content = build_glossary("What is an IPO?", Renderer("en"))
    assert content.related and all(title for _, title in content.related)


# --- D: the live calculator ---


def calc(client, **inputs):
    return client.post("/v1/calculate", json={"locale": "en", "inputs": inputs}).json()


def test_calculate_returns_scenarios_that_include_the_users_own_rate():
    data = calc(make_client(), tool="sip", monthly_inr=5000, months=120, rates_pct=[8])
    assert data["kind"] == "calculation" and data["is_illustration"] is True
    assert 8.0 in [s["assumption_pct"] for s in data["scenarios"]]
    assert len(data["scenarios"]) >= 2 and data["assumptions"]


def test_calculate_numbers_match_the_text_path_exactly():
    client = make_client()
    live = calc(client, tool="sip", monthly_inr=5000, months=120)
    text = analyze(client, "What will my SIP of 5000 a month look like over 10 years?")
    assert [s["values"] for s in live["scenarios"]] == [s["values"] for s in text["scenarios"]]


def test_calculate_asks_for_a_missing_number_instead_of_guessing():
    data = calc(make_client(), tool="sip", monthly_inr=5000)
    assert data["kind"] == "clarify"
    assert [q["field"] for q in data["questions"]] == ["calculation.months"]


def test_calculate_without_a_tool_asks_which_calculator():
    data = calc(make_client())
    assert data["kind"] == "clarify" and data["questions"][0]["field"] == "calculation.tool"
    assert len(data["questions"][0]["options"]) == 5


@pytest.mark.parametrize(
    "inputs",
    [
        {"tool": "sip", "monthly_inr": 5000, "months": 9999},
        {"tool": "sip", "monthly_inr": 0, "months": 12},
        {"tool": "consequence", "amount_inr": 1000, "leverage": 500},
        {"tool": "sip", "monthly_inr": 5000, "months": 12, "surprise": 1},
    ],
)
def test_calculate_rejects_out_of_range_or_unknown_input(inputs):
    response = make_client().post("/v1/calculate", json={"locale": "en", "inputs": inputs})
    assert response.status_code == 422
    assert "5000" not in response.text


def test_calculate_covers_every_calculator():
    client = make_client()
    cases = [
        {"tool": "goal", "goal_inr": 2000000, "months": 120},
        {"tool": "inflation", "amount_inr": 100000, "years": 10},
        {"tool": "consequence", "amount_inr": 50000, "leverage": 5, "drops_pct": [20]},
        {"tool": "costs", "trade_value_inr": 50000, "trades_per_month": 10},
    ]
    for inputs in cases:
        data = calc(client, **inputs)
        assert data["kind"] == "calculation", inputs
        assert data["tool"] == inputs["tool"] and len(data["scenarios"]) >= 2


def test_calculate_never_uses_prediction_wording():
    data = calc(make_client(), tool="sip", monthly_inr=5000, months=120, rates_pct=[15])
    text = json.dumps(data)
    for phrase in ("you will get", "you will earn", "expected return", "guaranteed"):
        assert phrase not in text.lower()


def test_calculate_is_listed_in_the_api_contract_schema():
    schema = make_client().get("/openapi.json").json()
    assert "/v1/calculate" in schema["paths"]


def test_a_warning_that_skipped_the_questions_carries_them_with_amount_hints():
    pause = analyze(make_client(), TIP + " Pay 5000 to rahul9876543210@ybl", profile=PROFILE)
    assert pause["level"] == "L3"
    by_field = {q["field"]: q for q in pause["refine"]}
    assert set(by_field) == {"amount_inr", "funding_source", "product_class"}
    assert [h["value"] for h in by_field["amount_inr"]["hints"]] == ["5000"]


def test_once_answered_the_pause_has_nothing_left_to_refine():
    pause = analyze(
        make_client(),
        TIP + " Pay 5000 to rahul9876543210@ybl",
        profile=PROFILE,
        answers={**ANSWERS, "amount_inr": 5000},
    )
    assert pause["refine"] == []


def test_a_skipped_question_is_not_offered_again_in_the_refine_list():
    pause = analyze(
        make_client(),
        TIP + " Pay 5000 to rahul9876543210@ybl",
        profile=PROFILE,
        answers={"skipped_fields": ["amount_inr"]},
    )
    assert pause["kind"] == "pause"
    assert {q["field"] for q in pause["refine"]} == {"funding_source", "product_class"}
