"""Stage 11: integration tests per endpoint, edge protections, executor and privacy."""

import base64
import json
import logging
import unicodedata

import pytest

from ruko.errors import ErrorCode, RukoError
from ruko.orchestrator.executor import ToolExecutor
from ruko.providers.llm.fake import FakeLLMProvider
from ruko.providers.speech.fake import FakeSpeechProvider
from tests.helpers import PROFILE, analyze_body, make_client, wav_b64

TIP = "Join our VIP group! BANKNIFTY 45000 CE, guaranteed 5% daily returns"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def error_code(response) -> str:
    return response.json()["error"]["code"]


# --- /v1/analyze ------------------------------------------------------------------------


@pytest.mark.parametrize("locale", ["en", "hi", "kn"])
def test_pause_signals_carry_severity_and_split_label(locale):
    client = make_client()
    body = analyze_body(
        TIP,
        locale=locale,
        profile=PROFILE,
        answers={"amount_inr": 40000, "funding_source": "borrowed"},
    )
    data = client.post("/v1/analyze", json=body).json()
    assert data["kind"] == "pause" and data["signals"]
    for signal in data["signals"]:
        assert signal["severity"] in ("low", "medium", "high")
        assert signal["certainty_label"] and signal["reason_text"]
        assert signal["text"] == f"{signal['certainty_label']}: {signal['reason_text']}"
        assert not signal["reason_text"].startswith(signal["certainty_label"])


def test_pause_event_summary_has_no_message_text():
    client = make_client()
    body = analyze_body(
        TIP, profile=PROFILE, answers={"amount_inr": 40000, "funding_source": "borrowed"}
    )
    data = client.post("/v1/analyze", json=body).json()
    event = data["event"]
    assert set(event) == {"stage", "action", "product_class", "source_type"}
    assert event["product_class"] == "derivative"
    assert "BANKNIFTY" not in json.dumps(event)


def test_content_report_signals_carry_split_label():
    client = make_client()
    data = client.post(
        "/v1/analyze", json=analyze_body("Is this message real? Guaranteed 5% daily returns")
    ).json()
    assert data["kind"] == "content_report"
    assert all(s["certainty_label"] and s["reason_text"] for s in data["signals"])


def test_analyze_pause_has_numbers_rules_signals_and_meta():
    client = make_client()
    body = analyze_body(
        TIP, profile=PROFILE, answers={"amount_inr": 40000, "funding_source": "borrowed"}
    )
    data = client.post("/v1/analyze", json=body).json()
    assert data["kind"] == "pause" and data["level"] in ("L2", "L3")
    assert data["numbers_text"][0] == "This decision: ₹40,000."
    assert "Your rule: no borrowed money." in data["rules_text"]
    assert all(s["certainty"] in ("likely", "possible", "unclear") for s in data["signals"])
    assert len(data["cards"]) <= 3
    assert data["decision"]["override_allowed"] is True
    meta = data["meta"]
    assert meta["extraction_mode"] == "llm" and meta["prompt_version"] == "extract-v3"
    assert meta["policy_version"] == "2" and meta["blocked_output_count"] == 0
    steps = [t["step"] for t in meta["trace"]]
    assert steps[:6] == [
        "detect_language", "intent_gate", "redact", "deterministic_signals", "stage", "llm_extract"
    ]  # fmt: skip
    assert meta["stage"] == "consider_action" and meta["stage_source"] == "user"
    assert steps[-2:] == ["engine", "render"]


def test_analyze_without_llm_falls_back_to_the_lexicon():
    client = make_client(llm=None)
    body = analyze_body(TIP, answers={"amount_inr": 1000, "funding_source": "savings"})
    data = client.post("/v1/analyze", json=body).json()
    assert data["meta"]["extraction_mode"] == "lexicon_only"
    llm_step = next(t for t in data["meta"]["trace"] if t["step"] == "llm_extract")
    assert llm_step["status"] == "skipped"
    assert "GUARANTEED_RETURN_CLAIM" in [s["code"] for s in data["signals"]]


def test_failing_llm_is_recorded_as_fallback():
    from ruko.providers.llm.base import LLMError

    client = make_client(llm=FakeLLMProvider([LLMError(ErrorCode.LLM_UNAVAILABLE, "timeout")]))
    body = analyze_body(TIP, answers={"amount_inr": 1000, "funding_source": "savings"})
    data = client.post("/v1/analyze", json=body).json()
    step = next(t for t in data["meta"]["trace"] if t["step"] == "llm_extract")
    assert step["status"] == "fallback" and data["meta"]["extraction_mode"] == "lexicon_only"


def test_screenshot_goes_through_ocr_then_the_same_pipeline():
    fake = FakeLLMProvider(['{"text": "Pay 18% tax first to withdraw your profits"}'])
    client = make_client(llm=fake)
    body = {"input": {"type": "image", "content": base64.b64encode(PNG).decode()}}
    data = client.post("/v1/analyze", json=body).json()
    assert data["kind"] == "pause" and data["level"] == "L3"
    assert [t["step"] for t in data["meta"]["trace"]][:2] == ["decode_image", "ocr"]


def test_screenshot_without_llm_is_ocr_unavailable():
    client = make_client(llm=None)
    body = {"input": {"type": "image", "content": base64.b64encode(PNG).decode()}}
    response = client.post("/v1/analyze", json=body)
    assert response.status_code == 503 and error_code(response) == "OCR_UNAVAILABLE"


def test_bad_screenshot_is_rejected():
    client = make_client()
    body = {"input": {"type": "image", "content": base64.b64encode(b"GIF89a....").decode()}}
    assert error_code(client.post("/v1/analyze", json=body)) == "IMAGE_FORMAT_UNSUPPORTED"


def test_unsupported_locale_is_a_typed_error():
    response = make_client().post("/v1/analyze", json=analyze_body("hello", locale="ta"))
    assert response.status_code == 422 and error_code(response) == "LOCALE_UNSUPPORTED"


def test_too_long_text_is_rejected():
    response = make_client(max_text_chars=50).post("/v1/analyze", json=analyze_body("x " * 40))
    assert response.status_code == 413


def test_response_locale_follows_detected_language():
    data = (
        make_client().post("/v1/analyze", json=analyze_body("ಹಣ ವಿತ್‌ಡ್ರಾ ಮಾಡಲು ಮೊದಲು ತೆರಿಗೆ ಕಟ್ಟಿ")).json()
    )
    assert data["meta"]["locale"] == "kn"


# --- /v1/analyze/voice -----------------------------------------------------------------


def test_voice_transcribes_then_analyzes():
    speech = [FakeSpeechProvider("Pay 18% tax first to withdraw your profits", "en")]
    client = make_client(speech=speech)
    body = {"audio_base64": wav_b64(), "audio_format": "wav"}
    data = client.post("/v1/analyze/voice", json=body).json()
    assert data["kind"] == "pause" and data["level"] == "L3"
    assert [t["step"] for t in data["meta"]["trace"]][:2] == ["decode_audio", "stt"]


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"audio_base64": wav_b64(), "audio_format": "mp3"}, "AUDIO_FORMAT_UNSUPPORTED"),
        ({"audio_base64": wav_b64(40.0), "audio_format": "wav"}, "AUDIO_TOO_LONG"),
    ],
)
def test_bad_voice_notes_are_rejected(body, code):
    assert error_code(make_client().post("/v1/analyze/voice", json=body)) == code


def test_no_speech_provider_is_speech_unavailable_but_text_still_works():
    client = make_client(speech=[])
    response = client.post(
        "/v1/analyze/voice", json={"audio_base64": wav_b64(), "audio_format": "wav"}
    )
    assert response.status_code == 503 and error_code(response) == "SPEECH_UNAVAILABLE"
    assert client.post("/v1/analyze", json=analyze_body("hello")).status_code == 200


# --- /v1/speak ---------------------------------------------------------------------------


def test_speak_reads_templates_from_a_previous_response():
    fake = FakeSpeechProvider()
    client = make_client(speech=[fake])
    pause = client.post("/v1/analyze", json=analyze_body(TIP, answers={"amount_inr": 40000,
                        "funding_source": "borrowed"}, profile=PROFILE)).json()  # fmt: skip
    data = client.post("/v1/speak", json={"locale": "hi", "items": pause["speak"][:10]}).json()
    assert data["kind"] == "speech" and data["provider"] == "fake"
    assert base64.b64decode(data["audio_base64"]).startswith(b"RIFF")
    locale, spoken = fake.spoken[0]
    assert locale == "hi"
    assert any("DEVANAGARI" in unicodedata.name(ch, "") for ch in spoken)


def test_speak_rejects_free_text_in_slots():
    client = make_client()
    body = {
        "locale": "en",
        "items": [{"key": "pause.numbers.amount", "slots": {"amount": "BUY NOW"}}],
    }
    assert error_code(client.post("/v1/speak", json=body)) == "INVALID_REQUEST"


# --- /v1/cards, /v1/recover, /v1/journal/review, /v1/order-intent, /v1/meta ----------------


def test_cards_endpoint():
    body = {
        "locale": "en",
        "event": {
            "is_financial_decision": True,
            "product_class": "derivative",
            "amount_inr": 20000,
        },
        "profile": PROFILE,
    }
    data = make_client().post("/v1/cards", json=body).json()
    assert data["kind"] == "cards" and data["cards"][0]["id"] == "leverage_rupees"


def test_recover_endpoint():
    body = {"locale": "kn", "answers": {"paid_money": True, "payment_method": "upi"}}
    data = make_client().post("/v1/recover", json=body).json()
    assert data["kind"] == "recovery" and data["scenario"] == "paid_scammer"
    assert data["steps"][0]["contact"] == "1930" and data["steps"][0]["urgent"]
    assert "recovery_routes:helpline_1930" in data["meta"]["unverified_fact_ids"]


def test_journal_review_endpoint():
    entry = {"id": "a", "date": "2026-09-30", "product_class": "derivative",
             "source_type": "unsolicited_group", "level_shown": "L2", "action": "went_ahead",
             "overrode": True, "followed_own_rules": False}  # fmt: skip
    body = {"locale": "en", "entries": [entry], "as_of": "2026-10-03"}
    data = make_client().post("/v1/journal/review", json=body).json()
    assert data["kind"] == "journal_review" and data["unsolicited_share_pct"] == 100.0
    assert data["overrides_without_reason"] == 1


def test_order_intent_returns_level_and_codes_only():
    body = {"product_class": "derivative", "amount_band": {"min_inr": 10000, "max_inr": 50000},
            "borrowed_funds": True, "plan_matched": True, "profile": PROFILE}  # fmt: skip
    data = make_client().post("/v1/order-intent", json=body).json()
    assert set(data) == {"kind", "level", "reason_codes", "override_allowed", "policy_version"}
    assert (
        "BORROWED_FUNDS" in data["reason_codes"]
        and "UNPLANNED_DECISION" not in data["reason_codes"]
    )


def test_order_intent_rejects_instrument_fields():
    body = {"product_class": "cash_equity", "amount_band": {"min_inr": 1, "max_inr": 2},
            "symbol": "XYZ"}  # fmt: skip
    assert make_client().post("/v1/order-intent", json=body).status_code == 422


def test_meta_endpoint_lists_languages_facts_and_providers_without_keys():
    data = make_client(gemini_api_key="secret-SENTINEL").get("/v1/meta").json()
    assert {lang["code"] for lang in data["languages"]} == {"en", "hi", "kn"}
    assert any(f["fact_id"] == "regulatory:capital_gains_listed_equity" for f in data["facts"])
    assert all(f["verified_by_human"] is False for f in data["facts"])
    assert data["providers"] == {"llm": True, "speech": True}
    assert "SENTINEL" not in json.dumps(data)


# --- Edge: size, content type, rate limit, CORS -----------------------------------------------


def test_wrong_content_type_is_415():
    response = make_client().post(
        "/v1/analyze", content=b"hello", headers={"content-type": "text/plain"}
    )
    assert response.status_code == 415 and error_code(response) == "UNSUPPORTED_MEDIA_TYPE"


def test_oversized_body_is_413():
    client = make_client(max_request_bytes=200)
    response = client.post("/v1/analyze", json=analyze_body("x" * 500))
    assert response.status_code == 413 and error_code(response) == "PAYLOAD_TOO_LARGE"


def test_rate_limit_is_429_after_the_limit():
    client = make_client(rate_limit_per_minute=2)
    codes = [client.get("/v1/meta").status_code for _ in range(3)]
    assert codes == [200, 200, 429]
    assert client.get("/health").status_code == 200  # health is not limited


def test_cors_only_for_configured_origins():
    client = make_client(cors_allow_origins=["https://app.example"])
    allowed = client.get("/v1/meta", headers={"origin": "https://app.example"})
    other = client.get("/v1/meta", headers={"origin": "https://evil.example"})
    assert allowed.headers.get("access-control-allow-origin") == "https://app.example"
    assert "access-control-allow-origin" not in other.headers


# --- Executor -------------------------------------------------------------------------


def test_executor_refuses_tools_outside_the_allow_list():
    executor = ToolExecutor()
    with pytest.raises(RukoError) as info:
        executor.run("send_whatsapp_message", lambda: None)
    assert info.value.code == ErrorCode.TOOL_NOT_ALLOWED


def test_executor_turns_unexpected_errors_into_tool_failed():
    executor = ToolExecutor()

    def broken() -> None:
        raise ValueError("secret content")

    with pytest.raises(RukoError) as info:
        executor.run("merge", broken)
    assert info.value.code == ErrorCode.TOOL_FAILED
    assert executor.trace[-1].status == "failed"


def test_allow_list_has_no_messaging_fetching_or_money_tools():
    from ruko.orchestrator.executor import allowed_tools

    for tool in allowed_tools():
        assert not any(word in tool for word in ("send", "fetch", "http", "pay", "transfer"))


# --- Privacy ------------------------------------------------------------------------------


def test_analyze_never_logs_or_echoes_message_content(caplog):
    sentinel = "ZEBRAQUARTZ"
    client = make_client()
    with caplog.at_level(logging.DEBUG):
        responses = [
            client.post(
                "/v1/analyze", json=analyze_body(f"{sentinel} guaranteed 5% daily returns")
            ),
            client.post("/v1/analyze", json=analyze_body(f"BANKNIFTY CE {sentinel} buy now")),
        ]
    assert all(sentinel not in r.text for r in responses)
    assert sentinel not in caplog.text
