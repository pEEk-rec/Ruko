"""Stage 6: LLM provider interface, Gemini over HTTP (mocked), fake provider, factory."""

import base64
import json

import httpx
import pytest
from pydantic import SecretStr

from ruko.config import Settings
from ruko.errors import ErrorCode
from ruko.providers.llm.base import ImagePart, LLMError, LLMRequest, Message
from ruko.providers.llm.factory import build_llm_provider
from ruko.providers.llm.fake import NEUTRAL_EXTRACTION, FakeLLMProvider
from ruko.providers.llm.gemini import GeminiProvider, build_body, parse_reply

KEY = "test-key-SENTINEL-123"
REQUEST = LLMRequest(system="sys", messages=(Message(role="user", text="hello"),))


def ok_payload(text: str = '{"a": 1}') -> dict:
    return {"candidates": [{"content": {"role": "model", "parts": [{"text": text}]}}]}


def make_provider(handler, max_retries: int = 2, sleeps: list | None = None) -> GeminiProvider:
    sleeps = sleeps if sleeps is not None else []
    return GeminiProvider(
        api_key=SecretStr(KEY),
        model="gemini-test",
        base_url="https://example.invalid/v1beta",
        timeout_seconds=1.0,
        max_retries=max_retries,
        transport=httpx.MockTransport(handler),
        sleep=sleeps.append,
    )


def test_gemini_request_shape_and_key_in_header_only():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=ok_payload())

    image = ImagePart(mime_type="image/png", data=b"\x89PNGdata")
    request = LLMRequest(
        system="system text",
        messages=(Message(role="user", text="look", image=image),),
    )
    assert make_provider(handler).generate(request) == '{"a": 1}'
    sent = seen[0]
    assert sent.url.path.endswith("/models/gemini-test:generateContent")
    assert sent.headers["x-goog-api-key"] == KEY
    assert KEY not in str(sent.url)
    body = json.loads(sent.content)
    assert body["systemInstruction"]["parts"][0]["text"] == "system text"
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert body["generationConfig"]["temperature"] == 0
    parts = body["contents"][0]["parts"]
    assert body["contents"][0]["role"] == "user"
    assert parts[0] == {"text": "look"}
    assert base64.b64decode(parts[1]["inlineData"]["data"]) == b"\x89PNGdata"
    assert parts[1]["inlineData"]["mimeType"] == "image/png"


def test_plain_text_request_has_no_json_mime_type():
    body = build_body(LLMRequest(system="s", messages=REQUEST.messages, json_output=False))
    assert "responseMimeType" not in body["generationConfig"]


def test_parse_reply_joins_text_and_skips_thoughts():
    payload = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": "thinking", "thought": True},
                        {"text": '{"x":'},
                        {"text": "1}"},
                    ]
                }
            }
        ]
    }
    assert parse_reply(payload) == '{"x":1}'


@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        ({"promptFeedback": {"blockReason": "SAFETY"}}, "blocked"),
        ({"candidates": []}, "empty"),
        (
            {"candidates": [{"content": {"parts": [{"text": "  "}]}, "finishReason": "SAFETY"}]},
            "empty",
        ),
    ],
)
def test_blocked_or_empty_reply_is_invalid_output(payload, reason):
    with pytest.raises(LLMError) as info:
        parse_reply(payload)
    assert info.value.code == ErrorCode.LLM_INVALID_OUTPUT
    assert info.value.reason == reason


def test_retries_transient_errors_with_backoff_then_succeeds():
    statuses = iter([503, 429, 200])
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        status = next(statuses)
        return httpx.Response(status, json=ok_payload() if status == 200 else {})

    assert make_provider(handler, sleeps=sleeps).generate(REQUEST) == '{"a": 1}'
    assert sleeps == [0.5, 1.0]


def test_gives_up_after_max_retries_with_typed_error():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(429, json={})

    with pytest.raises(LLMError) as info:
        make_provider(handler, max_retries=2).generate(REQUEST)
    assert info.value.code == ErrorCode.LLM_UNAVAILABLE
    assert info.value.reason == "http_429"
    assert len(calls) == 3


def test_client_errors_are_not_retried():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(400, json={"error": {"message": "bad"}})

    with pytest.raises(LLMError) as info:
        make_provider(handler).generate(REQUEST)
    assert info.value.reason == "http_400"
    assert len(calls) == 1


def test_timeouts_are_retried_then_reported():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(LLMError) as info:
        make_provider(handler, max_retries=1).generate(REQUEST)
    assert info.value.code == ErrorCode.LLM_UNAVAILABLE
    assert info.value.reason == "timeout"


def test_key_never_appears_in_repr_or_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={})

    provider = make_provider(handler)
    assert KEY not in repr(provider)
    with pytest.raises(LLMError) as info:
        provider.generate(REQUEST)
    assert KEY not in str(info.value) and KEY not in repr(info.value)


def test_image_part_repr_hides_bytes():
    assert "secretbytes" not in repr(ImagePart("image/png", b"secretbytes"))


def test_fake_provider_scripts_replies_errors_and_records_calls():
    error = LLMError(ErrorCode.LLM_UNAVAILABLE, "timeout")
    fake = FakeLLMProvider(["first", error, lambda req: req.system])
    assert fake.generate(REQUEST) == "first"
    with pytest.raises(LLMError):
        fake.generate(REQUEST)
    assert fake.generate(REQUEST) == "sys"
    assert fake.generate(REQUEST) == NEUTRAL_EXTRACTION
    text_request = LLMRequest(system="s", messages=REQUEST.messages, json_output=False)
    assert json.loads(fake.generate(text_request)) == {"text": ""}
    assert len(fake.calls) == 5


@pytest.mark.parametrize(
    ("mode", "key", "expected"),
    [
        ("none", "k", None),
        ("fake", None, FakeLLMProvider),
        ("auto", None, None),
        ("auto", "k", GeminiProvider),
        ("gemini", None, None),
        ("gemini", "k", GeminiProvider),
    ],
)
def test_factory_chooses_provider(mode, key, expected):
    settings = Settings(llm_provider=mode, gemini_api_key=SecretStr(key) if key else None)
    provider = build_llm_provider(settings)
    if expected is None:
        assert provider is None
    else:
        assert isinstance(provider, expected)


def test_understanding_modules_have_no_network_code():
    import inspect

    from ruko.understanding import clarify, extract, merge, screenshot

    for module in (extract, merge, clarify, screenshot):
        source = inspect.getsource(module)
        for banned in ("import httpx", "urllib", "import requests", "import socket"):
            assert banned not in source, (module.__name__, banned)
