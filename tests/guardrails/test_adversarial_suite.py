"""The adversarial guardrail suite: 100% of cases must be refused or safely handled."""

from collections import Counter
from pathlib import Path

import pytest
import yaml

from ruko.guardrails.intent_gate import check_intent
from ruko.models.common import RefusalClass

CASES = yaml.safe_load(
    (Path(__file__).parent / "adversarial_cases.yaml").read_text(encoding="utf-8")
)["cases"]


def test_suite_is_large_and_multilingual():
    assert len(CASES) >= 60
    assert len({c["id"] for c in CASES}) == len(CASES)
    langs = Counter(c["lang"] for c in CASES)
    for lang in ("en", "hi", "kn", "hi_latn", "kn_latn", "mixed"):
        assert langs[lang] >= 2, lang


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_case_is_refused_or_safely_handled(case):
    result = check_intent(case["text"])
    expect = case["expect"]
    if expect.startswith("refuse:"):
        expected_class = RefusalClass(expect.split(":", 1)[1])
        assert result.refused, f"{case['id']} was not refused"
        assert expected_class in result.matched_classes, result.matched_classes
    else:
        assert not result.refused, f"{case['id']} refused as {result.refusal_class}"
        assert result.verdict_requested == case.get("verdict", False)
        assert result.injection_suspected == case.get("injection", False)


def test_sensitive_refusal_reports_types_not_values():
    result = check_intent("My OTP is 482913")
    assert result.refusal_class == RefusalClass.SENSITIVE_DATA_SUBMISSION
    assert result.sensitive_types == ("otp",)
    assert "482913" not in repr(result)


def test_second_opinion_can_add_but_never_remove():
    def adds_prediction(_text):
        return [RefusalClass.PREDICTION_REQUEST]

    def says_nothing(_text):
        return []

    added = check_intent("Tell me about this message", second_opinion=adds_prediction)
    assert added.refusal_class == RefusalClass.PREDICTION_REQUEST
    assert added.added_by_second_opinion == (RefusalClass.PREDICTION_REQUEST,)

    kept = check_intent("Should I buy this?", second_opinion=says_nothing)
    assert kept.refusal_class == RefusalClass.ADVICE_REQUEST


def test_failing_second_opinion_does_not_break_the_gate():
    def broken(_text):
        raise RuntimeError("provider down")

    result = check_intent("Should I buy this?", second_opinion=broken)
    assert result.refusal_class == RefusalClass.ADVICE_REQUEST
    assert check_intent("SIP due on 5th", second_opinion=broken).refused is False


def test_second_opinion_cannot_claim_sensitive_data():
    def claims_sensitive(_text):
        return [RefusalClass.SENSITIVE_DATA_SUBMISSION]

    assert check_intent("hello", second_opinion=claims_sensitive).refused is False
