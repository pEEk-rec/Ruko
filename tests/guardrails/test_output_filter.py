"""Assertion-level output validator: what Ruko asserts vs what it reports, in every language."""

import pytest
from pydantic import BaseModel

from ruko.guardrails.output_filter import filter_text, find_violations
from ruko.guardrails.output_validator import (
    get_output_policy,
    response_violations,
    user_facing_texts,
    validate,
)
from ruko.language.templates import Renderer, get_template_store

# Always forbidden, whatever the response type.
ALWAYS = [
    ("en", "You should buy this stock now", "trade_directive"),
    ("en", "I recommend this fund for you", "trade_directive"),
    ("en", "Strong buy signal on this share", "trade_directive"),
    ("en", "The stock will go up tomorrow", "price_prediction"),
    ("en", "Target ₹450, SL 380", "price_prediction"),
    ("en", "Open an account with Zerodha today", "named_product_or_broker"),
    ("en", "Try Binance for crypto", "named_product_or_broker"),
    ("en", "Y0u sh0uld buy th1s n0w", "trade_directive"),
    ("en", "This message is a scam.", "verdict"),
    ("en", "The app looks like a fraud.", "verdict"),
    ("hi", "ये शेयर खरीदें", "trade_directive"),
    ("hi", "कल ये शेयर बढ़ेगा", "price_prediction"),
    ("hi", "यह मैसेज स्कैम है", "verdict"),
    ("hi_latn", "abhi kharid lo bhai", "trade_directive"),
    ("hi_latn", "ye scam hai", "verdict"),
    ("kn", "ಈ ಷೇರು ಖರೀದಿಸಿ", "trade_directive"),
    ("kn", "ನಾಳೆ ಬೆಲೆ ಏರುತ್ತದೆ", "price_prediction"),
    ("kn", "ಇದು ಸ್ಕ್ಯಾಮ್", "verdict"),
    ("kn_latn", "ee share tagoli", "trade_directive"),
]

# Ruko ASSERTING a claim: blocked in every response type, even ones that may report claims.
ASSERTIONS = [
    ("en", "Guaranteed returns of 20% every year", "return_claim"),
    ("en", "Earn 3% daily with our platform", "return_claim"),
    ("en", "You will double your money in a month", "return_claim"),
    ("en", "This scheme is safe and legit", "safety_claim"),
    ("en", "It is a genuine investment", "safety_claim"),
    ("en", "This is guaranteed.", "safety_claim"),
    ("en", "This app is safe.", "safety_claim"),
    ("hi", "पक्का मुनाफा मिलेगा", "return_claim"),
    ("hi", "यह स्कीम सुरक्षित है", "safety_claim"),
    ("hi_latn", "guarantee return milega", "return_claim"),
    ("hi_latn", "ye app safe hai", "safety_claim"),
    ("kn", "ಖಚಿತ ಲಾಭ ಸಿಗುತ್ತದೆ", "return_claim"),
    ("kn", "ಇದು ಸುರಕ್ಷಿತ ಆಗಿದೆ", "safety_claim"),
]

# Ruko REPORTING a claim: allowed for signal reports and cards, in every language.
REPORTS = [
    "This message contains a guaranteed-return claim.",
    "The message says the returns are guaranteed.",
    "The group claims 5% daily returns.",
    "They say the app is safe and legit.",
    "SEBI's rules do not allow registered advisers to promise assured returns.",
    "Ruko can't vouch for any tip, app or person, and no one can promise guaranteed returns.",
    "मैसेज में गारंटीड रिटर्न का दावा है।",
    "मैसेज कहता है कि यह ऐप सुरक्षित है।",
    "ಮೆಸೇಜ್‌ನಲ್ಲಿ ಖಚಿತ ಲಾಭದ ಭರವಸೆ ಇದೆ.",
    "ಈ ಆ್ಯಪ್ ಸುರಕ್ಷಿತ ಆಗಿದೆ ಎಂದು ಮೆಸೇಜ್ ಹೇಳುತ್ತದೆ.",
    "Group message mein pakka munafa ka dava hai.",
]

CLEAN = [
    "If the price moves 5% against you, that is ₹2,000 of your ₹40,000.",
    "This is about 4 months of your expenses.",
    "You said this money is borrowed.",
    "Your rule: no more than 10% of savings in one decision.",
    "Ruko doesn't tell anyone what to buy, sell or keep.",
    "What is your plan if this goes wrong?",
    "इस फ़ैसले का आपके अपने पैसों के लिए क्या मतलब है?",
    "ಇದು ನಿಮ್ಮ ಖರ್ಚಿನ ಸುಮಾರು 4 ತಿಂಗಳು.",
    "SEBI's study looked at a group of traders; it is not a prediction for you.",
]


@pytest.mark.parametrize(("lang", "text", "category"), ALWAYS, ids=[v[1] for v in ALWAYS])
@pytest.mark.parametrize("response_type", ["strict", "signal_report", "card", "headline"])
def test_always_forbidden_in_every_response_type(lang, text, category, response_type):
    assert category in validate(text, response_type)


@pytest.mark.parametrize(("lang", "text", "category"), ASSERTIONS, ids=[v[1] for v in ASSERTIONS])
@pytest.mark.parametrize("response_type", ["strict", "signal_report", "card", "headline"])
def test_ruko_asserting_a_claim_is_blocked(lang, text, category, response_type):
    assert category in validate(text, response_type)


@pytest.mark.parametrize("text", REPORTS)
@pytest.mark.parametrize("response_type", ["signal_report", "card", "content_report"])
def test_reporting_a_claim_is_not_blocked(text, response_type):
    assert validate(text, response_type) == []


@pytest.mark.parametrize("text", REPORTS[:6])
@pytest.mark.parametrize("response_type", ["headline", "exposure_summary", "strict"])
def test_claims_are_not_reportable_in_other_response_types(text, response_type):
    if any(word in text.lower() for word in ("guaranteed", "assured", "safe", "5% daily")):
        assert validate(text, response_type) != []


@pytest.mark.parametrize("text", CLEAN)
def test_clean_text_passes_strictly(text):
    assert find_violations(text) == []


def test_claim_and_frame_must_be_in_the_same_sentence():
    text = "The message mentions a group. Guaranteed returns."
    assert "return_claim" in validate(text, "signal_report")


def test_blocked_text_is_replaced_and_only_category_recorded():
    result = filter_text("You should buy this now", "safe fallback")
    assert result.blocked
    assert result.text == "safe fallback"
    assert result.categories == ("trade_directive",)


def test_bad_fallback_is_a_data_bug():
    with pytest.raises(ValueError):
        filter_text("Buy this now", "Guaranteed returns")


def test_every_template_passes_for_its_declared_response_type():
    store = get_template_store()
    policy = get_output_policy()
    failures = []
    for locale in store.locales():
        for key in store.keys(locale):
            template = store.get(locale, key)
            assert policy.known_type(template.response_type), (locale, key)
            sample = template.text.format_map(dict.fromkeys(template.slots, "12"))
            if validate(sample, template.response_type):
                failures.append((locale, key, validate(sample, template.response_type)))
    assert failures == []


def test_renderer_counts_blocked_output_without_keeping_it():
    renderer = Renderer(locale="hi")
    safe = renderer.filtered("You should buy this stock now")
    assert renderer.blocked_count == 1
    assert safe == renderer.raw("output.blocked_fallback")


class _Inner(BaseModel):
    text: str
    source_url: str


class _Response(BaseModel):
    headline: str
    items: list[_Inner]
    request_id: str


def test_response_level_check_walks_user_facing_fields_only():
    response = _Response(
        headline="This app is safe.",
        items=[_Inner(text="Fine.", source_url="https://example.invalid/safe-app-is-safe")],
        request_id="This is a scam",  # not user-facing: ignored
    )
    assert user_facing_texts(response) == ["This app is safe.", "Fine."]
    assert response_violations(response) == ["safety_claim"]
