"""Validation tests for v1 request bodies."""

import pytest
from pydantic import ValidationError

from ruko.models.requests import (
    AmountBand,
    AnalyzeRequest,
    JournalReviewRequest,
    OrderIntentRequest,
    RecoverRequest,
    SpeakRequest,
    VoiceAnalyzeRequest,
)


def test_analyze_request_minimal_and_round_trip():
    req = AnalyzeRequest.model_validate({"input": {"type": "text", "content": "hello"}})
    assert req.profile.rules.no_borrowed_money is False
    assert AnalyzeRequest.model_validate_json(req.model_dump_json()) == req


def test_analyze_request_rejects_unknown_answer_fields():
    with pytest.raises(ValidationError):
        AnalyzeRequest.model_validate(
            {"input": {"type": "text", "content": "x"}, "answers": {"otp": "123456"}}
        )


def test_voice_request_needs_known_format():
    with pytest.raises(ValidationError):
        VoiceAnalyzeRequest(audio_base64="AAAA", audio_format="exe")


def test_speak_request_needs_items_and_caps_them():
    with pytest.raises(ValidationError):
        SpeakRequest(locale="en", items=[])
    with pytest.raises(ValidationError):
        SpeakRequest(locale="en", items=[{"key": "k"}] * 11)


def test_order_intent_has_no_instrument_or_user_fields():
    fields = set(OrderIntentRequest.model_fields)
    assert fields == {
        "product_class", "amount_band", "borrowed_funds", "leveraged", "plan_matched", "profile"
    }  # fmt: skip
    with pytest.raises(ValidationError):
        OrderIntentRequest.model_validate(
            {"product_class": "derivative", "amount_band": {"min_inr": 1, "max_inr": 2},
             "symbol": "XYZ"}
        )  # fmt: skip


def test_amount_band_must_be_ordered():
    with pytest.raises(ValidationError):
        AmountBand(min_inr=10, max_inr=5)


def test_recover_and_journal_requests_validate():
    RecoverRequest(locale="kn", answers={"paid_money": True, "payment_method": "upi"})
    JournalReviewRequest(locale="hi", entries=[])
    with pytest.raises(ValidationError):
        RecoverRequest(locale="kn", answers={"paid_money": True, "account_number": "1234"})
