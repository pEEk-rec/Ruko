"""Stage 6: LLM provider interface, Gemini via the Gen AI SDK (fake client), fake, factory."""

import json

import httpx
import pytest
from google.genai import errors, types
from pydantic import SecretStr

from ruko.config import Settings
from ruko.errors import ErrorCode
from ruko.providers.llm.base import ImagePart, LLMError, LLMRequest, Message
from ruko.providers.llm.factory import build_llm_provider
from ruko.providers.llm.fake import NEUTRAL_EXTRACTION, FakeLLMProvider
from ruko.providers.llm.gemini import GeminiProvider, build_config, parse_response

KEY = "test-key-SENTINEL-123"
REQUEST = LLMRequest(system="sys", messages=(Message(role="user", text="hello"),))


def reply(*parts: types.Part) -> types.GenerateContentResponse:
    content = types.Content(role="model", parts=list(parts) or [types.Part(text='{"a": 1}')])
    return types.GenerateContentResponse(candidates=[types.Candidate(content=content)])


class FakeModels:
    """Stands in for ``client.models``: scripted replies or exceptions, records calls."""

    def __init__(self, script: list) -> None:
        self.script = list(script)
        self.calls: list[dict] = []

    def generate_content(self, **kwargs: object) -> types.GenerateContentResponse:
        self.calls.append(kwargs)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeClient:
    def __init__(self, script: list) -> None:
        self.models = FakeModels(script)


def make_provider(script: list, max_retries: int = 2, sleeps: list | None = None):
    client = FakeClient(script)
    provider = GeminiProvider(
        api_key=SecretStr(KEY),
        model="gemini-test",
        timeout_seconds=1.0,
        max_retries=max_retries,
        client=client,
        sleep=(sleeps if sleeps is not None else []).append,
    )
    return provider, client.models


def api_error(code: int) -> errors.APIError:
    return errors.APIError(code, {"error": {"code": code, "status": "X", "message": "m"}})


def test_gemini_request_shape():
    provider, models = make_provider([reply()])
    image = ImagePart(mime_type="image/png", data=b"PNGdata")
    request = LLMRequest(system="system text", messages=(Message("user", "look", image),))
    assert provider.generate(request) == '{"a": 1}'
    call = models.calls[0]
    assert call["model"] == "gemini-test"
    content = call["contents"][0]
    assert content.role == "user" and content.parts[0].text == "look"
    assert content.parts[1].inline_data.data == b"PNGdata"
    assert content.parts[1].inline_data.mime_type == "image/png"
    config = call["config"]
    assert config.system_instruction == "system text"
    assert config.temperature == 0 and config.response_mime_type == "application/json"


def test_plain_text_request_has_no_json_mime_type():
    config = build_config(LLMRequest(system="s", messages=REQUEST.messages, json_output=False))
    assert config.response_mime_type is None


def test_parse_reply_joins_text_and_skips_thoughts():
    response = reply(
        types.Part(text="thinking", thought=True), types.Part(text='{"x":'), types.Part(text="1}")
    )
    assert parse_response(response) == '{"x":1}'


@pytest.mark.parametrize(
    ("response", "reason"),
    [
        (
            types.GenerateContentResponse(
                prompt_feedback=types.GenerateContentResponsePromptFeedback(block_reason="SAFETY")
            ),
            "blocked",
        ),
        (types.GenerateContentResponse(candidates=[]), "empty"),
        (reply(types.Part(text="  ")), "empty"),
    ],
)
def test_blocked_or_empty_reply_is_invalid_output(response, reason):
    with pytest.raises(LLMError) as info:
        parse_response(response)
    assert info.value.code == ErrorCode.LLM_INVALID_OUTPUT
    assert info.value.reason == reason


def test_retries_transient_errors_with_backoff_then_succeeds():
    sleeps: list[float] = []
    provider, models = make_provider([api_error(503), api_error(429), reply()], sleeps=sleeps)
    assert provider.generate(REQUEST) == '{"a": 1}'
    assert sleeps == [0.5, 1.0] and len(models.calls) == 3


def test_gives_up_after_max_retries_with_typed_error():
    provider, models = make_provider([api_error(429)] * 3, max_retries=2)
    with pytest.raises(LLMError) as info:
        provider.generate(REQUEST)
    assert info.value.code == ErrorCode.LLM_UNAVAILABLE
    assert info.value.reason == "http_429" and len(models.calls) == 3


def test_client_errors_are_not_retried():
    provider, models = make_provider([api_error(400)])
    with pytest.raises(LLMError) as info:
        provider.generate(REQUEST)
    assert info.value.reason == "http_400" and len(models.calls) == 1


def test_timeouts_and_network_errors_are_retried_then_reported():
    request = httpx.Request("POST", "https://example.invalid")
    provider, _ = make_provider([httpx.ReadTimeout("slow", request=request)] * 2, max_retries=1)
    with pytest.raises(LLMError) as info:
        provider.generate(REQUEST)
    assert info.value.reason == "timeout"
    provider, _ = make_provider([httpx.ConnectError("down", request=request)], max_retries=0)
    with pytest.raises(LLMError) as info:
        provider.generate(REQUEST)
    assert info.value.reason == "network"


def test_key_never_appears_in_repr_or_errors():
    provider, _ = make_provider([api_error(401)])
    assert KEY not in repr(provider)
    with pytest.raises(LLMError) as info:
        provider.generate(REQUEST)
    assert KEY not in str(info.value) and KEY not in repr(info.value)


def test_real_client_is_built_from_settings_without_network():
    provider = GeminiProvider.from_settings(
        Settings(gemini_api_key=SecretStr(KEY), gemini_model="gemini-x")
    )
    assert provider.model == "gemini-x" and KEY not in repr(provider)


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


def test_out_of_quota_on_the_main_model_falls_back_once_to_the_fallback_model():
    client = FakeClient([api_error(429), api_error(429), api_error(429), reply()])
    provider = GeminiProvider(
        api_key=SecretStr(KEY), model="main", timeout_seconds=1.0, max_retries=2,
        fallback_model="spare", client=client, sleep=[].append,
    )  # fmt: skip
    assert provider.generate(REQUEST) == '{"a": 1}'
    assert [c["model"] for c in client.models.calls] == ["main", "main", "main", "spare"]


def test_other_errors_do_not_use_the_fallback_and_no_fallback_means_the_error_stands():
    client = FakeClient([api_error(400)])
    provider = GeminiProvider(
        api_key=SecretStr(KEY), model="main", timeout_seconds=1.0, max_retries=2,
        fallback_model="spare", client=client, sleep=[].append,
    )  # fmt: skip
    with pytest.raises(LLMError):
        provider.generate(REQUEST)
    assert [c["model"] for c in client.models.calls] == ["main"]
    plain, models = make_provider([api_error(429)] * 3)
    with pytest.raises(LLMError):
        plain.generate(REQUEST)
    assert len(models.calls) == 3


def test_after_running_out_of_quota_the_fallback_is_used_directly_for_a_while():
    now = [0.0]
    client = FakeClient([api_error(429), reply(), reply(), api_error(429), reply()])
    provider = GeminiProvider(
        api_key=SecretStr(KEY), model="main", timeout_seconds=1.0, max_retries=0,
        fallback_model="spare", client=client, sleep=[].append, clock=lambda: now[0],
    )  # fmt: skip
    provider.generate(REQUEST)
    provider.generate(REQUEST)  # straight to the spare, no wasted call
    now[0] = 601.0
    provider.generate(REQUEST)  # quota window over: main is tried again first
    assert [c["model"] for c in client.models.calls] == ["main", "spare", "spare", "main", "spare"]
