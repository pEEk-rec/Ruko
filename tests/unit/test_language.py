"""Stage 3: detection, redaction, number words, templates and the template linter."""

import re
import string

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from ruko.language.detect import detect_language
from ruko.language.numbers import amount_in_words, group_indian, number_in_words, rupees
from ruko.language.redact import redact
from ruko.language.template_lint import lint_templates
from ruko.language.templates import Renderer, Template, TemplateStore, get_template_store
from ruko.models.inputs import Script

# ---------------------------------------------------------------- detection


@pytest.mark.parametrize(
    ("text", "language", "script", "mixed", "romanized"),
    [
        ("Should I buy this stock now?", "en", Script.LATIN, False, False),
        ("क्या मुझे ये शेयर खरीदना चाहिए?", "hi", Script.DEVANAGARI, False, False),
        ("ಈ ಷೇರು ನಾಳೆ ಏರುತ್ತಾ?", "kn", Script.KANNADA, False, False),
        ("bhai ye share kab tak hold karu, bahut gir gaya hai", "hi", Script.LATIN, False, True),
        ("naanu ee share tagobeka, nimma opinion enu", "kn", Script.LATIN, False, True),
        ("ಈ stock ನಾನು buy ಮಾಡಬೇಕಾ? market is up", "kn", Script.MIXED, True, False),
        ("ये stock कल buy करूँ? market is very strong today", "hi", Script.MIXED, True, False),
        (
            "is this the right time? kya main abhi karu ya nahi, please tell",
            "hi",
            Script.LATIN,
            True,
            True,
        ),
    ],
)
def test_detection(text, language, script, mixed, romanized):
    result = detect_language(text)
    assert (result.language, result.script, result.is_code_mixed, result.is_romanized) == (
        language,
        script,
        mixed,
        romanized,
    )
    assert 0.0 <= result.confidence <= 1.0


def test_detection_without_letters_uses_default_with_zero_confidence():
    result = detect_language("12345 ₹ 678", default="kn")
    assert result.language == "kn"
    assert result.confidence == 0.0


# ---------------------------------------------------------------- redaction

phones = st.from_regex(r"[6-9][0-9]{9}", fullmatch=True)
names = st.text(alphabet=string.ascii_lowercase, min_size=3, max_size=10)


@settings(max_examples=150, deadline=None)
@given(phone=phones, user=names, psp=st.sampled_from(["oksbi", "ybl", "paytm", "okaxis"]))
def test_redaction_never_leaks_phone_or_upi(phone, user, psp):
    text = f"Call {phone} or pay {user}.k@{psp} or {phone}@{psp} today"
    result = redact(text)
    assert phone not in result.text
    assert f"{user}.k" not in result.text
    assert result.counts["phone"] == 1
    assert result.counts["upi_id"] == 2


@settings(max_examples=150, deadline=None)
@given(digits=st.from_regex(r"[1-9][0-9]{10,15}", fullmatch=True))
def test_redaction_never_leaks_long_numbers(digits):
    result = redact(f"Transfer to A/C {digits} now")
    assert digits not in result.text
    assert sum(result.counts.values()) == 1


@settings(max_examples=100, deadline=None)
@given(local=names, domain=names)
def test_redaction_never_leaks_email(local, domain):
    email = f"{local}@{domain}.com"
    result = redact(f"mail me at {email}")
    assert email not in result.text
    assert result.counts == {"email": 1}


@pytest.mark.parametrize(
    ("text", "expected", "counts"),
    [
        ("pay ramesh.k@oksbi", "pay [UPI_USER]@oksbi", {"upi_id": 1}),
        ("pay 9876543210@ybl", "pay [UPI_PHONE]@ybl", {"upi_id": 1}),
        ("pay abc.brk@validhdfc", "pay [UPI_USER].brk@validhdfc", {"upi_id": 1}),
        ("call +91 98765 43210", "call [PHONE]", {"phone": 1}),
        ("PAN ABCDE1234F", "PAN [PAN]", {"pan": 1}),
        ("card 4111 1111 1111 1111", "card [CARD]", {"card": 1}),
        ("Contact Mr. Ramesh Kumar", "Contact Mr [NAME]", {"name": 1}),
        ("श्री रमेश से बात करें", "श्री [NAME] से बात करें", {"name": 1}),
        ("Rs 10,000 and Rs 100000000 and IFSC SBIN0001234", None, {}),
        ("amounts 10000 20000 on 2024-10-05", None, {}),
    ],
)
def test_redaction_examples(text, expected, counts):
    result = redact(text)
    assert result.text == (expected if expected is not None else text)
    assert result.counts == counts


# ---------------------------------------------------------------- numbers


@pytest.mark.parametrize(
    ("n", "grouped"),
    [(0, "0"), (99, "99"), (999, "999"), (1000, "1,000"), (100000, "1,00,000"),
     (15000000, "1,50,00,000"), (1234567890, "1,23,45,67,890"), (-150000, "-1,50,000")],
)  # fmt: skip
def test_indian_grouping(n, grouped):
    assert group_indian(n) == grouped


@given(st.integers(min_value=0, max_value=10**15))
def test_grouping_property(n):
    text = group_indian(n)
    assert text.replace(",", "") == str(n)
    groups = text.split(",")
    assert len(groups[-1]) == 3 or len(groups) == 1
    assert all(len(g) == 2 for g in groups[1:-1])


@pytest.mark.parametrize(
    ("n", "en", "hi", "kn"),
    [
        (0, "zero rupees", "शून्य रुपये", "ಸೊನ್ನೆ ರೂಪಾಯಿ"),
        (1, "one rupee", "एक रुपया", "ಒಂದು ರೂಪಾಯಿ"),
        (99, "ninety-nine rupees", "निन्यानवे रुपये", "ತೊಂಬತ್ತೊಂಬತ್ತು ರೂಪಾಯಿ"),
        (100000, "one lakh rupees", "एक लाख रुपये", "ಒಂದು ಲಕ್ಷ ರೂಪಾಯಿ"),
        (
            15000000,
            "one crore fifty lakh rupees",
            "एक करोड़ पचास लाख रुपये",
            "ಒಂದು ಕೋಟಿ ಐವತ್ತು ಲಕ್ಷ ರೂಪಾಯಿ",
        ),
        (150000, "one lakh fifty thousand rupees", "एक लाख पचास हज़ार रुपये",
         "ಒಂದು ಲಕ್ಷ ಐವತ್ತು ಸಾವಿರ ರೂಪಾಯಿ"),
    ],
)  # fmt: skip
def test_amount_in_words_edge_cases(n, en, hi, kn):
    assert amount_in_words(n, "en") == en
    assert amount_in_words(n, "hi") == hi
    assert amount_in_words(n, "kn") == kn


def test_rupee_formatting():
    assert rupees(150000) == "₹1,50,000"


_EN_UNITS = [
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen",
    "nineteen",
]  # fmt: skip
_EN_VALUES = {w: i for i, w in enumerate(_EN_UNITS)}
_EN_TENS = {
    w: (i + 2) * 10
    for i, w in enumerate(
        ["twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
    )
}
_EN_SCALES = {"crore": 10**7, "lakh": 10**5, "thousand": 10**3}


def _parse_en(words: str) -> int:
    total, current = 0, 0
    for token in words.split():
        for part in token.split("-"):
            if part in _EN_VALUES:
                current += _EN_VALUES[part]
            elif part in _EN_TENS:
                current += _EN_TENS[part]
            elif part == "hundred":
                current *= 100
            elif part == "crore":
                total = (total + current) * 10**7
                current = 0
            else:
                total += current * _EN_SCALES[part]
                current = 0
    return total + current


@settings(max_examples=300)
@given(st.integers(min_value=0, max_value=10**12))
def test_english_words_round_trip(n):
    assert _parse_en(number_in_words(n, "en")) == n


@settings(max_examples=200)
@given(st.integers(min_value=0, max_value=10**12), st.sampled_from(["en", "hi", "kn"]))
def test_words_never_contain_digits(n, locale):
    words = number_in_words(n, locale)
    assert words and not re.search(r"\d", words)


# ---------------------------------------------------------------- templates


def test_template_linter_is_green():
    assert lint_templates() == []


def test_linter_reports_missing_keys_slot_mismatch_and_filter_violations():
    store = TemplateStore(
        {
            "en": {
                "a": Template("a", "You have {n} rules", "draft"),
                "b": Template("b", "Fine", "draft"),
                "c": Template("c", "Guaranteed returns", "draft"),
            },
            "hi": {"a": Template("a", "आपके नियम", "draft")},
        }
    )
    problems = lint_templates(store=store)
    assert "missing hi: b" in problems
    assert "slots differ hi: a" in problems
    assert any(p.startswith("output validator en: c") for p in problems)


def test_missing_key_falls_back_to_english_and_is_recorded():
    store = get_template_store()
    custom = TemplateStore(
        {
            "en": {
                **{k: store.get("en", k) for k in store.keys("en")},
                "only.en": Template("only.en", "Hello {name}", "draft"),
            },
            "kn": {k: store.get("kn", k) for k in store.keys("kn")},
        }
    )
    renderer = Renderer(locale="kn", store=custom)
    assert renderer.text("only.en", name="Asha") == "Hello Asha"
    assert renderer.missing_keys == ["only.en"]
    assert renderer.draft_count == 1


def test_every_template_has_a_valid_status():
    store = get_template_store()
    for locale in store.locales():
        for key in store.keys(locale):
            assert store.get(locale, key).status in ("draft", "human_verified")
