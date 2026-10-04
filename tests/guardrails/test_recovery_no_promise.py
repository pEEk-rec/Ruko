"""Recovery text never promises a refund, a reversal or zero liability (owner rule, 4 Oct 2026).

RBI's zero / limited liability rules cover unauthorised transactions; a payment the user
made to a scammer usually is not one. Ruko only says where to report, fast.
"""

import pytest

from ruko.guardrails.output_validator import validate
from ruko.language.templates import get_template_store

LOCALES = ("en", "hi", "kn")
RECOVERY_TYPES = ("recovery_step", "recovery_draft")


def _recovery_templates(locale: str):
    store = get_template_store()
    for key in sorted(store.keys(locale)):
        template = store.get(locale, key)
        if "recover" in key and template is not None:
            yield key, template


@pytest.mark.parametrize("locale", LOCALES)
def test_every_recovery_template_passes_the_no_promise_rule(locale):
    checked = 0
    for key, template in _recovery_templates(locale):
        text = template.text.replace("{helpline}", "1930")
        for response_type in RECOVERY_TYPES:
            assert validate(text, response_type) == [], f"{locale}:{key}"
        checked += 1
    assert checked >= 20


@pytest.mark.parametrize(
    "text",
    [
        "Your bank will refund the money.",
        "You have zero liability for this payment.",
        "Call now and you will get your money back.",
        "The payment will be reversed within a week.",
        "Don't worry, the amount will be returned.",
        "आपको पैसे वापस मिल जाएंगे।",
        "बैंक से रिफंड मिलेगा।",
        "ನಿಮ್ಮ ಹಣ ವಾಪಸ್ ಸಿಗುತ್ತದೆ.",
        "ಬ್ಯಾಂಕ್ ರೀಫಂಡ್ ಮಾಡುತ್ತದೆ.",
    ],
)
@pytest.mark.parametrize("response_type", [*RECOVERY_TYPES, "recovery"])
def test_refund_promises_are_blocked(text, response_type):
    assert f"{response_type}_assertion" in validate(text, response_type)


@pytest.mark.parametrize(
    ("locale", "negation"),
    [("en", "can't promise"), ("hi", "वादा नहीं"), ("kn", "ಸಾಧ್ಯವಿಲ್ಲ")],
)
def test_no_promise_line_is_a_denial(locale, negation):
    template = get_template_store().get(locale, "recovery.no_promise")
    assert template is not None and negation in template.text
