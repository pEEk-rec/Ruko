"""Output filter: blocks forbidden content in every language; templates pass it."""

import pytest

from ruko.guardrails.output_filter import filter_text, find_violations
from ruko.language.templates import Renderer, get_template_store

VIOLATIONS = [
    ("en", "You should buy this stock now", "trade_directive"),
    ("en", "I recommend this fund for you", "trade_directive"),
    ("en", "Strong buy signal on this share", "trade_directive"),
    ("en", "Guaranteed returns of 20% every year", "return_promise"),
    ("en", "Earn 3% daily with our platform", "return_promise"),
    ("en", "You will double your money in a month", "return_promise"),
    ("en", "This scheme is safe and legit", "safety_claim"),
    ("en", "It is a genuine investment", "safety_claim"),
    ("en", "The stock will go up tomorrow", "price_prediction"),
    ("en", "Target ₹450, SL 380", "price_prediction"),
    ("en", "Open an account with Zerodha today", "named_product_or_broker"),
    ("en", "Try Binance for crypto", "named_product_or_broker"),
    ("en", "Y0u sh0uld buy th1s n0w", "trade_directive"),
    ("hi", "ये शेयर खरीदें", "trade_directive"),
    ("hi", "पक्का मुनाफा मिलेगा", "return_promise"),
    ("hi", "यह स्कीम सुरक्षित है", "safety_claim"),
    ("hi", "कल ये शेयर बढ़ेगा", "price_prediction"),
    ("hi_latn", "abhi kharid lo bhai", "trade_directive"),
    ("hi_latn", "guarantee return milega", "return_promise"),
    ("hi_latn", "ye app safe hai", "safety_claim"),
    ("kn", "ಈ ಷೇರು ಖರೀದಿಸಿ", "trade_directive"),
    ("kn", "ಖಚಿತ ಲಾಭ ಸಿಗುತ್ತದೆ", "return_promise"),
    ("kn", "ಇದು ಸುರಕ್ಷಿತ ಆಗಿದೆ", "safety_claim"),
    ("kn", "ನಾಳೆ ಬೆಲೆ ಏರುತ್ತದೆ", "price_prediction"),
    ("kn_latn", "ee share tagoli", "trade_directive"),
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


@pytest.mark.parametrize(("lang", "text", "category"), VIOLATIONS, ids=[v[1] for v in VIOLATIONS])
def test_violations_are_found(lang, text, category):
    assert category in find_violations(text)


@pytest.mark.parametrize("text", CLEAN)
def test_clean_text_passes(text):
    assert find_violations(text) == []


def test_blocked_text_is_replaced_and_only_category_recorded():
    result = filter_text("You should buy this now", "safe fallback")
    assert result.blocked
    assert result.text == "safe fallback"
    assert result.categories == ("trade_directive",)


def test_bad_fallback_is_a_data_bug():
    with pytest.raises(ValueError):
        filter_text("Buy this now", "Guaranteed returns")


def test_every_template_in_every_locale_passes_the_filter():
    store = get_template_store()
    failures = [
        (locale, key, find_violations(store.get(locale, key).text))
        for locale in store.locales()
        for key in store.keys(locale)
        if find_violations(store.get(locale, key).text)
    ]
    assert failures == []


def test_renderer_counts_blocked_output_without_keeping_it():
    renderer = Renderer(locale="hi")
    safe = renderer.filtered("You should buy this stock now")
    assert renderer.blocked_count == 1
    assert safe == renderer.raw("output.blocked_fallback")
