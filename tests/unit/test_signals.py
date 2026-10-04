"""Deterministic signal detection (lexicon, links, payments)."""

import inspect

import pytest

from ruko.language.redact import redact
from ruko.models.common import Certainty, PaymentDestination, ReasonCode
from ruko.understanding import lexicon, links, payments
from ruko.understanding.lexicon import detect_hints, detect_signals
from ruko.understanding.links import analyze_link, extract_links, link_signals
from ruko.understanding.payments import analyze_payments, payment_destination, payment_signals

R = ReasonCode
LIKELY, POSSIBLE = Certainty.LIKELY, Certainty.POSSIBLE


def all_signals(text: str) -> dict[ReasonCode, Certainty]:
    redacted = redact(text).text
    found = {s.code: s.certainty for s in detect_signals(redacted)}
    for signal in link_signals(redacted)[0] + payment_signals(analyze_payments(redacted)):
        if found.get(signal.code) != LIKELY:
            found[signal.code] = signal.certainty
    return found


LEXICON_CASES = [
    # English
    ("en", "Guaranteed returns every month, zero risk", R.GUARANTEED_RETURN_CLAIM, LIKELY),
    ("en", "Earn 3% daily on your capital", R.GUARANTEED_RETURN_CLAIM, LIKELY),
    ("en", "Sure shot calls for this week", R.GUARANTEED_RETURN_CLAIM, POSSIBLE),
    ("en", "Hurry up and decide", R.URGENCY_PRESSURE, POSSIBLE),
    ("en", "Hurry, offer closes tonight", R.URGENCY_PRESSURE, LIKELY),
    ("en", "Last chance! Only 5 seats left, pay now", R.URGENCY_PRESSURE, LIKELY),
    ("en", "We are a SEBI registered advisory", R.AUTHORITY_CLAIM, POSSIBLE),
    ("en", "Profit screenshots are in the group", R.PROFIT_SCREENSHOT_SOCIAL_PROOF, POSSIBLE),
    ("en", "Join our VIP group for premium calls", R.UNSOLICITED_SOURCE, LIKELY),
    ("en", "Download our app to start trading", R.APP_INSTALL_REQUEST, LIKELY),
    ("en", "Install AnyDesk so our team can help you", R.APP_INSTALL_REQUEST, LIKELY),
    ("en", "Pay 18% tax first to withdraw your profits", R.WITHDRAWAL_FEE_DEMAND, LIKELY),
    ("en", "A release fee is needed for your funds", R.WITHDRAWAL_FEE_DEMAND, LIKELY),
    ("en", "Send it to my GPay", R.PAY_TO_INDIVIDUAL_ACCOUNT, POSSIBLE),
    ("en", "Send the amount to my personal UPI", R.PAY_TO_INDIVIDUAL_ACCOUNT, LIKELY),
    ("en", "This is the SEBI officer handling your case", R.IMPERSONATION_SUSPECTED, POSSIBLE),
    ("en", "SEBI notice: pay the penalty fee today", R.IMPERSONATION_SUSPECTED, LIKELY),
    # Hindi (Devanagari)
    ("hi", "पक्का मुनाफा हर महीने", R.GUARANTEED_RETURN_CLAIM, LIKELY),
    ("hi", "जल्दी करें, सिर्फ आज", R.URGENCY_PRESSURE, LIKELY),
    ("hi", "हम सेबी रजिस्टर्ड हैं", R.AUTHORITY_CLAIM, POSSIBLE),
    ("hi", "प्रॉफिट के स्क्रीनशॉट देखें", R.PROFIT_SCREENSHOT_SOCIAL_PROOF, POSSIBLE),
    ("hi", "वीआईपी ग्रुप में आइए", R.UNSOLICITED_SOURCE, POSSIBLE),
    ("hi", "हमारा ऐप डाउनलोड करें", R.APP_INSTALL_REQUEST, LIKELY),
    ("hi", "पैसे निकालने के लिए पहले टैक्स भरना होगा", R.WITHDRAWAL_FEE_DEMAND, LIKELY),
    ("hi", "इस नंबर पर पैसे भेजें", R.PAY_TO_INDIVIDUAL_ACCOUNT, POSSIBLE),
    ("hi", "आपका खाता ब्लॉक हो जाएगा", R.IMPERSONATION_SUSPECTED, POSSIBLE),
    # Romanized Hindi
    ("hi_latn", "pakka munafa milega bhai", R.GUARANTEED_RETURN_CLAIM, LIKELY),
    ("hi_latn", "jaldi karo, sirf aaj", R.URGENCY_PRESSURE, LIKELY),
    ("hi_latn", "nikalne ke liye pehle tax pay karo", R.WITHDRAWAL_FEE_DEMAND, LIKELY),
    ("hi_latn", "app download karo abhi", R.APP_INSTALL_REQUEST, LIKELY),
    # Kannada
    ("kn", "ದಿನಕ್ಕೆ 2% ಖಚಿತ ಲಾಭ", R.GUARANTEED_RETURN_CLAIM, LIKELY),
    ("kn", "ಇಂದು ಮಾತ್ರ, ಸೀಟು ಸೀಮಿತ", R.URGENCY_PRESSURE, LIKELY),
    ("kn", "ನಾವು ಸೆಬಿ ನೋಂದಾಯಿತ ಸಂಸ್ಥೆ", R.AUTHORITY_CLAIM, POSSIBLE),
    ("kn", "ಲಾಭದ ಸ್ಕ್ರೀನ್‌ಶಾಟ್ ನೋಡಿ", R.PROFIT_SCREENSHOT_SOCIAL_PROOF, POSSIBLE),
    ("kn", "ವಿಐಪಿ ಗ್ರೂಪ್ ಸೇರಿ", R.UNSOLICITED_SOURCE, LIKELY),
    ("kn", "ನಮ್ಮ ಆ್ಯಪ್ ಡೌನ್‌ಲೋಡ್ ಮಾಡಿ", R.APP_INSTALL_REQUEST, LIKELY),
    ("kn", "ಹಣ ವಿತ್‌ಡ್ರಾ ಮಾಡಲು ಮೊದಲು ತೆರಿಗೆ ಕಟ್ಟಿ", R.WITHDRAWAL_FEE_DEMAND, LIKELY),
    ("kn", "ನಿಮ್ಮ ಖಾತೆ ಫ್ರೀಜ್ ಆಗುತ್ತದೆ", R.IMPERSONATION_SUSPECTED, POSSIBLE),
    ("kn", "ನನ್ನ ಯುಪಿಐಗೆ ಹಣ ಕಳುಹಿಸಿ", R.PAY_TO_INDIVIDUAL_ACCOUNT, POSSIBLE),
    # Romanized Kannada
    ("kn_latn", "dinakke 2% guarantee labha", R.GUARANTEED_RETURN_CLAIM, LIKELY),
    ("kn_latn", "indu matra offer", R.URGENCY_PRESSURE, POSSIBLE),
    ("kn_latn", "app download madi", R.APP_INSTALL_REQUEST, LIKELY),
]


@pytest.mark.parametrize(
    ("lang", "text", "code", "certainty"), LEXICON_CASES, ids=[c[1][:40] for c in LEXICON_CASES]
)
def test_lexicon_pattern(lang, text, code, certainty):
    found = {s.code: s.certainty for s in detect_signals(text)}
    assert code in found, f"{lang}: {code} not found"
    assert found[code] == certainty


def test_every_lexicon_code_is_tested_in_every_language():
    tested = {(lang[:2], code) for lang, _, code, _ in LEXICON_CASES}
    lexicon_codes = {p.code for p in lexicon.load_patterns()}
    missing = [
        (lang, c) for c in lexicon_codes for lang in ("en", "hi", "kn") if (lang, c) not in tested
    ]
    assert missing == []


def test_signals_carry_evidence_spans():
    signal = detect_signals("Guaranteed returns every month")[0]
    assert signal.evidence is not None
    assert signal.evidence.end > signal.evidence.start


LEGITIMATE = [
    "Your SIP of Rs 5,000 in XYZ Flexicap Fund is due on 5th. Ensure balance.",
    "Your order to buy 10 shares of XYZ was executed at 450.25. Contract note sent to email.",
    "Dividend of Rs 120 credited to your bank account for XYZ Ltd shares.",
    "IPO allotment status: check on the registrar website. Refunds will be processed by 25th.",
    "Muhurat trading on Diwali from 6 PM to 7 PM. Markets closed on Friday.",
    "Mutual fund investments are subject to market risks, read all scheme documents carefully.",
    "Your KYC has been successfully verified. Thank you.",
    "Annual statement for your demat account is available on the depository website.",
    "Reminder: your insurance premium of Rs 12,000 is due next week.",
    "Kal market band rahega, Diwali muhurat trading 6 baje",
    "आपकी SIP की किस्त 5 तारीख को कटेगी।",
    "ನಿಮ್ಮ SIP ಕಂತು 5ನೇ ತಾರೀಖಿನಂದು ಕಡಿತವಾಗುತ್ತದೆ.",
    "Visit https://www.sebi.gov.in or https://scores.sebi.gov.in for investor information.",
    "Read the annual report at https://www.nseindia.com/companies-listing",
    "My friend bought some Infosys shares last year for long term.",
]


@pytest.mark.parametrize("text", LEGITIMATE)
def test_no_false_positives_on_ordinary_messages(text):
    assert all_signals(text) == {}


# ------------------------------------------------------------------ links


@pytest.mark.parametrize(
    ("link", "features", "brand"),
    [
        ("https://bit.ly/3xYz", {"shortener"}, None),
        ("https://t.me/joinchat/abc", {"messaging_invite"}, None),
        ("https://chat.whatsapp.com/Invite123", {"messaging_invite"}, None),
        ("http://example.com/files/trade.apk", {"no_https", "apk"}, None),
        ("http://103.21.44.9/login", {"no_https", "ip_host"}, None),
        ("https://sebi-kyc-update.in", {"lookalike"}, "sebi"),
        ("nsdl-kyc.in", {"lookalike"}, "nsdl"),
        ("https://www.nsekyc.com/verify", {"lookalike"}, "nse"),
        ("https://sebl.gov.in.co/notice", {"lookalike"}, "sebi"),
        ("https://xn--80ak6aa92e.com", {"punycode"}, None),
    ],
)
def test_link_features(link, features, brand):
    finding = analyze_link(link)
    assert set(finding.features) == features
    assert finding.lookalike_of == brand


@pytest.mark.parametrize(
    "link",
    ["https://www.sebi.gov.in/legal", "https://scores.sebi.gov.in", "https://www.nseindia.com",
     "https://www.license.com", "https://www.bsestar-example.com", "https://www.example.com"],
)  # fmt: skip
def test_official_and_ordinary_links_have_no_features(link):
    assert analyze_link(link).features == ()


def test_link_signals_and_certainty():
    signals = {s.code: s.certainty for s in link_signals("Update KYC at http://nsdl-kyc.in")[0]}
    assert signals[R.IMPERSONATION_SUSPECTED] == LIKELY
    assert signals[R.UNVERIFIED_PLATFORM_LINK] == LIKELY
    one = {s.code: s.certainty for s in link_signals("details: https://bit.ly/abc")[0]}
    assert one == {R.UNVERIFIED_PLATFORM_LINK: POSSIBLE}
    invite = {s.code for s in link_signals("join t.me/stocksguru now")[0]}
    assert R.UNSOLICITED_SOURCE in invite


def test_extract_links_finds_bare_domains_and_trims_punctuation():
    assert extract_links("go to nsdl-kyc.in, then www.x.com.") == ["nsdl-kyc.in", "www.x.com"]


def test_link_and_signal_modules_never_fetch():
    for module in (links, lexicon, payments):
        source = inspect.getsource(module)
        for forbidden in (
            "import httpx",
            "import requests",
            "urllib.request",
            "import socket",
            "urlopen(",
        ):
            assert forbidden not in source, (module.__name__, forbidden)


# ------------------------------------------------------------------ payments


@pytest.mark.parametrize(
    ("text", "certainty", "destination"),
    [
        ("Deposit to 9876543210@ybl now", LIKELY, PaymentDestination.INDIVIDUAL_ACCOUNT),
        ("Pay Rs 10,000 to ramesh.k@oksbi", POSSIBLE, PaymentDestination.UNKNOWN),
        ("Pay to A/C 123456789012 IFSC SBIN0001234", POSSIBLE, PaymentDestination.UNKNOWN),
        ("Scan the QR and pay to activate", POSSIBLE, PaymentDestination.UNKNOWN),
        ("Pay brokerage via abc.brk@validhdfc", None, PaymentDestination.UNKNOWN),
        ("My UPI is ramesh.k@oksbi", None, PaymentDestination.UNKNOWN),
    ],
)
def test_payment_classification(text, certainty, destination):
    findings = analyze_payments(redact(text).text)
    signals = payment_signals(findings)
    assert (signals[0].certainty if signals else None) == certainty
    assert payment_destination(findings) == destination


def test_validated_handle_pattern_is_recorded_not_trusted():
    findings = analyze_payments(redact("Pay via abc.brk@validhdfc").text)
    assert findings.upi_validated_pattern == 1
    assert payment_destination(findings) != PaymentDestination.BROKER_OR_EXCHANGE


def test_validated_suffix_on_ordinary_handle_is_not_validated():
    findings = analyze_payments(redact("Pay to abc.brk@oksbi").text)
    assert findings.upi_validated_pattern == 0 and findings.upi_other == 1


def test_payment_findings_hold_no_values():
    findings = analyze_payments(redact("Deposit to 9876543210@ybl").text)
    assert "9876543210" not in repr(findings)


# ------------------------------------------------------------------ hints


def test_hints_for_fallback_extraction():
    assert detect_hints("BANKNIFTY 48000 CE expiry today")["product_class"][0] == "derivative"
    assert detect_hints("SIP in an index fund")["product_class"] == ["mutual_fund"]
    assert detect_hints("intraday BTST call")["holding_intent"] == ["intraday"]
    assert detect_hints("my friend said buy")["source_type"] == ["known_person"]
    assert detect_hints("Nothing here") == {}
