"""v2: decision stages, glossary, content report and the show_unverified_facts setting."""

import pytest

from ruko.cards.glossary import build_glossary, find_term, get_glossary
from ruko.cards.select import select_cards
from ruko.config import Settings
from ruko.engine.engine import decide
from ruko.guardrails.output_filter import find_violations
from ruko.language.redact import redact
from ruko.language.templates import Renderer
from ruko.models.common import DecisionStage as S
from ruko.models.common import PaymentDestination, ReasonCode
from ruko.models.event import DecisionEvent
from ruko.models.profile import UserProfile
from ruko.models.requests import PaymentMethod, RecoveryAnswers
from ruko.models.responses import ResponseMeta
from ruko.orchestrator.content_report import build_content_report
from ruko.recovery.guide import build_guide
from ruko.understanding.extract import ExtractionOutcome
from ruko.understanding.merge import collect_deterministic, merge
from ruko.understanding.stage import (
    classify_stage,
    matched_stages,
    recovery_answers_from_text,
    resolve,
)

# --- Stage classification -----------------------------------------------------------

STAGE_CASES = [
    ("en", "What is a stop loss order?", S.LEARN),
    ("en", "Could you explain what a mutual fund is", S.LEARN),
    ("en", "Is this message genuine or a scam?", S.EVALUATE_CONTENT),
    ("en", "Can I trust this Telegram channel?", S.EVALUATE_CONTENT),
    ("en", "I have already sent Rs 4000 to their account", S.ALREADY_ACTED),
    ("en", "The platform wants a 10% tax before releasing my money", S.ALREADY_ACTED),
    ("en", "Unable to withdraw from the app since Monday", S.ALREADY_ACTED),
    ("en", "I'm placing this options order right now", S.ABOUT_TO_ACT),
    ("en", "About to transfer the joining fee", S.ABOUT_TO_ACT),
    ("en", "Planning to invest in a small cap fund next month", S.CONSIDER_ACTION),
    ("hi", "म्यूचुअल फ़ंड किसे कहते हैं?", S.LEARN),
    ("hi", "क्या यह ग्रुप वाला मैसेज असली है?", S.EVALUATE_CONTENT),
    ("hi", "मैंने कल उनके खाते में 3000 जमा कर दिए", S.ALREADY_ACTED),
    ("hi", "अभी यह फ़ंड खरीद रहा हूँ", S.ABOUT_TO_ACT),
    ("hi", "शेयर में थोड़ा पैसा लगाने की सोच रही हूँ", S.CONSIDER_ACTION),
    ("hi_latn", "stop loss kya hota hai", S.LEARN),
    ("hi_latn", "maine unko 2000 bhej diye", S.ALREADY_ACTED),
    ("kn", "ಮ್ಯೂಚುವಲ್ ಫಂಡ್ ಎಂದರೇನು?", S.LEARN),
    ("kn", "ಈ ಲಿಂಕ್ ನಿಜವೇ?", S.EVALUATE_CONTENT),
    ("kn", "ನಾನು ಅವರಿಗೆ ಹಣ ಕಳುಹಿಸಿದ್ದೇನೆ", S.ALREADY_ACTED),
    ("kn", "ಷೇರುಗಳಲ್ಲಿ ಹೂಡಬೇಕು ಅಂತ ಯೋಚಿಸುತ್ತಿದ್ದೇನೆ", S.CONSIDER_ACTION),
    ("kn_latn", "nav andre enu", S.LEARN),
]


@pytest.mark.parametrize(("lang", "text", "stage"), STAGE_CASES, ids=[c[1] for c in STAGE_CASES])
def test_stage_patterns(lang, text, stage):
    assert classify_stage(text).stage == stage


def test_already_acted_mixed_with_acting_asks_instead_of_guessing():
    text = "I paid 500 yesterday and I'm thinking of buying more"
    assert {S.ALREADY_ACTED, S.CONSIDER_ACTION} <= matched_stages(text)
    assert classify_stage(text).stage == S.UNKNOWN


def test_plan_example_paid_then_add_more():
    # BUILD_PLAN v2 Stage 5: "I paid 500 yesterday, should I add more?" mixes stages.
    text = "I paid ₹500 yesterday, should I add more?"
    assert classify_stage(text).stage == S.UNKNOWN  # stage level: ask, do not assume fraud
    from ruko.guardrails.intent_gate import check_intent

    assert check_intent(text).refusal_class.value == "ADVICE_REQUEST"  # gate runs first
    softer = "I paid ₹500 yesterday and I want to add more"
    assert classify_stage(softer).stage == S.UNKNOWN


def test_tie_break_order():
    assert resolve({S.LEARN, S.EVALUATE_CONTENT}) == S.EVALUATE_CONTENT
    assert resolve({S.EVALUATE_CONTENT, S.ABOUT_TO_ACT}) == S.ABOUT_TO_ACT
    assert resolve({S.ALREADY_ACTED, S.LEARN}) == S.ALREADY_ACTED
    assert resolve(set()) is None


def test_declared_stage_and_defaults():
    assert classify_stage("anything", declared=S.LEARN).source == "user"
    assert classify_stage("BANKNIFTY", declared_amount=True).stage == S.CONSIDER_ACTION
    shared = classify_stage("Join our VIP group today", looks_financial=True)
    assert shared.stage == S.CONSIDER_ACTION and shared.source == "default"
    assert classify_stage("good morning everyone").stage == S.UNKNOWN


def test_forwarded_scam_text_is_not_mistaken_for_the_users_own_report():
    # A scam message *demanding* a fee is content, not the user saying they paid.
    text = "Your profit is ready. Pay 18% tax to withdraw it."
    assert classify_stage(text, looks_financial=True).stage == S.CONSIDER_ACTION


# --- Recovery pre-fill from an already_acted report -------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("I already paid Rs 5000 through PhonePe", {"paid_money": True, "payment_method": "upi"}),
        (
            "I sent the amount by NEFT yesterday",
            {"paid_money": True, "payment_method": "bank_transfer"},
        ),
        (
            "I downloaded their app and shared my screen",
            {"installed_app": True, "paid_money": False},
        ),
        ("They want a fee before I can withdraw", {"cannot_withdraw": True}),
        ("There is an order in my demat that I never placed", {"unauthorized_trade": True}),
    ],
)
def test_recovery_answers_from_text(text, expected):
    answers = recovery_answers_from_text(text)
    for key, value in expected.items():
        assert getattr(answers, key) == value, key


def test_recovery_prefill_never_extracts_identifiers():
    answers = recovery_answers_from_text("I paid 9876543210@ybl Rs 5000, ref 123456789012")
    assert set(answers.model_dump()) == set(RecoveryAnswers.model_fields)
    assert answers.payment_method in set(PaymentMethod)


def test_payment_destination_implies_upi():
    answers = recovery_answers_from_text(
        "I already paid them", PaymentDestination.INDIVIDUAL_ACCOUNT
    )
    assert answers.payment_method == PaymentMethod.UPI


# --- Glossary ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "term"),
    [("What is an IPO?", "ipo"), ("NAV kya hota hai", "nav"), ("ಡಿಮ್ಯಾಟ್ ಖಾತೆ ಎಂದರೇನು", "demat"),
     ("मार्जिन का मतलब क्या है", "margin"), ("explain f&o", "fno"), ("What is a stop loss?", None)],
)  # fmt: skip
def test_glossary_lookup(text, term):
    found = find_term(text)
    assert (found.id if found else None) == term


@pytest.mark.parametrize("locale", ["en", "hi", "kn"])
def test_every_glossary_entry_renders_with_a_source(locale):
    for term in get_glossary().terms:
        renderer = Renderer(locale)
        content = build_glossary(f"what is {term.id}", renderer)
        assert content.found and content.title and content.body
        assert content.sources and renderer.blocked_count == 0
        assert renderer.missing_keys == []


def test_unknown_term_gets_the_official_pointer():
    content = build_glossary("What is a Bollinger band?", Renderer("en"))
    assert not content.found and content.term is None
    assert content.sources[0].source_url.startswith("https://investor.sebi.gov.in")
    assert "not in Ruko's glossary" in content.body


@pytest.mark.usefixtures("unverified_facts")
def test_glossary_hides_unverified_pointers_when_asked():
    content = build_glossary("What is an IPO?", Renderer("en"), show_unverified=False)
    assert content.found and content.sources == []


# --- Content report -------------------------------------------------------------------


def _event(text: str) -> DecisionEvent:
    redacted = redact(text).text
    return merge(collect_deterministic(redacted), ExtractionOutcome(mode="lexicon_only")).event


def test_content_report_lists_signals_with_severity_and_no_verdict():
    report = build_content_report(
        _event("Pay 18% tax first to withdraw your profits"), Renderer("en")
    )
    signals = report.fields["signals"]
    assert [s.code for s in signals] == [ReasonCode.WITHDRAWAL_FEE_DEMAND]
    assert signals[0].severity.value == "high"
    assert report.fields["recovery_entry"] is not None
    assert all(c.safety_critical for c in report.fields["cards"])
    texts = [report.fields["headline"], *(s.text for s in signals)]
    assert all(not find_violations(t, "content_report") for t in texts)
    assert "can't vouch" in report.fields["headline"]


def test_content_report_with_nothing_found_says_so_without_vouching():
    report = build_content_report(_event("See you at dinner"), Renderer("hi"))
    assert report.fields["signals"] == [] and report.fields["note"]
    assert report.fields["recovery_entry"] is None


# --- show_unverified_facts -------------------------------------------------------------------


def test_setting_defaults_by_environment_and_can_be_overridden():
    assert Settings(environment="dev").unverified_facts_visible is True
    assert Settings(environment="prod").unverified_facts_visible is False
    assert Settings(environment="prod", show_unverified_facts=True).unverified_facts_visible


@pytest.mark.usefixtures("unverified_facts")
def test_cards_with_unverified_facts_are_hidden_in_production():
    event = DecisionEvent(
        is_financial_decision=True, product_class="derivative", amount_inr=40000,
        funding_source="borrowed",
    )  # fmt: skip
    profile = UserProfile(age_band="lt_30", liquid_savings_band="1l_3l")
    decision = decide(event, profile)
    dev = select_cards(event, decision, profile, Renderer("en"))
    prod = select_cards(event, decision, profile, Renderer("en"), show_unverified=False)
    assert "group_base_rate" in [c.id for c in dev.cards]
    assert [c.id for c in prod.cards] == ["leverage_rupees"]  # arithmetic only, no facts
    assert prod.unverified_fact_ids == []


@pytest.mark.usefixtures("unverified_facts")
def test_recovery_hides_unverified_routes_in_production():
    answers = RecoveryAnswers(paid_money=True, payment_method="upi")
    meta = ResponseMeta(request_id="t", locale="en")
    dev = build_guide(answers, Renderer("en"), meta)
    prod = build_guide(answers, Renderer("en"), meta, show_unverified=False)
    assert dev.steps[0].contact == "1930" and "1930" in dev.steps[0].text
    assert all(s.route_id is None for s in prod.steps)
    assert prod.sources == []
