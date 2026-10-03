"""Stage 7: speech providers, audio limits, fallback order, speaking templates only."""

import base64
import json

import httpx
import pytest
from pydantic import SecretStr

from ruko.config import Settings
from ruko.errors import ErrorCode, RukoError
from ruko.language.speak import build_speech_text
from ruko.language.speech_codes import locale_for_speech_code, speech_code_for
from ruko.language.templates import Renderer, Template, TemplateStore
from ruko.models.responses import TemplateRef
from ruko.providers.speech.audio import decode_audio, wav_duration
from ruko.providers.speech.base import AudioClip, SpeechError
from ruko.providers.speech.factory import SpeechChain, build_speech_chain
from ruko.providers.speech.fake import FakeSpeechProvider, silent_wav
from ruko.providers.speech.sarvam import SarvamProvider

KEY = "sarvam-SENTINEL-key"
MAX_BYTES, MAX_SECONDS = 100_000, 30.0


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


# --- Audio checks ---------------------------------------------------------------------

SAMPLES = {
    "mp3": b"ID3\x03\x00" + b"\x00" * 20,
    "ogg": b"OggS" + b"\x00" * 20,
    "opus": b"OggS" + b"\x00" * 20,
    "webm": b"\x1a\x45\xdf\xa3" + b"\x00" * 20,
    "m4a": b"\x00\x00\x00\x20ftypM4A " + b"\x00" * 12,
    "aac": b"\xff\xf1\x50\x80" + b"\x00" * 20,
    "flac": b"fLaC" + b"\x00" * 20,
    "amr": b"#!AMR\n" + b"\x00" * 20,
}


@pytest.mark.parametrize("fmt", sorted(SAMPLES))
def test_declared_formats_are_accepted_when_magic_bytes_match(fmt):
    clip = decode_audio(b64(SAMPLES[fmt]), fmt, MAX_BYTES, MAX_SECONDS)
    assert clip.format == fmt and clip.duration_seconds is None


def test_wav_duration_is_measured():
    clip = decode_audio(b64(silent_wav(2.0)), "wav", MAX_BYTES, MAX_SECONDS)
    assert clip.duration_seconds == pytest.approx(2.0)
    assert wav_duration(b"not a wav") is None


@pytest.mark.parametrize(
    ("content", "fmt", "code"),
    [
        (b64(SAMPLES["flac"]), "mp3", ErrorCode.AUDIO_FORMAT_UNSUPPORTED),
        (b64(SAMPLES["mp3"]), "wav", ErrorCode.AUDIO_FORMAT_UNSUPPORTED),
        (b64(b"RIFF\x00\x00\x00\x00WAVEbroken"), "wav", ErrorCode.AUDIO_FORMAT_UNSUPPORTED),
        ("%%% not base64 %%%", "wav", ErrorCode.AUDIO_FORMAT_UNSUPPORTED),
        (b64(b"ID3" + b"\x00" * 200_000), "mp3", ErrorCode.AUDIO_TOO_LARGE),
        (b64(silent_wav(31.0, rate=1000)), "wav", ErrorCode.AUDIO_TOO_LONG),
    ],
    ids=["flac-as-mp3", "mp3-as-wav", "broken-wav", "not-base64", "too-large", "too-long"],
)
def test_bad_audio_is_rejected_with_typed_errors(content, fmt, code):
    with pytest.raises(RukoError) as info:
        decode_audio(content, fmt, MAX_BYTES, MAX_SECONDS)
    assert info.value.code == code


def test_audio_reprs_hide_bytes():
    assert "secret" not in repr(AudioClip(b"secret", "wav"))


# --- Locale mapping (data-driven) ----------------------------------------------------------


def test_speech_codes_come_from_the_language_registry():
    assert [speech_code_for(x) for x in ("en", "hi", "kn")] == ["en-IN", "hi-IN", "kn-IN"]
    assert speech_code_for("ta") is None
    assert locale_for_speech_code("KN-in") == "kn"
    assert locale_for_speech_code("xx-YY") is None


# --- Sarvam over HTTP (mocked) ------------------------------------------------------------


def sarvam(handler, max_retries: int = 1, sleeps: list | None = None) -> SarvamProvider:
    return SarvamProvider(
        SecretStr(KEY),
        base_url="https://example.invalid",
        stt_model="saaras:v4",
        tts_model="bulbul:v3",
        tts_speaker="shubh",
        tts_max_chars=50,
        timeout_seconds=1.0,
        max_retries=max_retries,
        transport=httpx.MockTransport(handler),
        sleep=(sleeps if sleeps is not None else []).append,
    )


def test_sarvam_stt_request_and_reply():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"transcript": "ನಮಸ್ಕಾರ", "language_code": "kn-IN"})

    clip = AudioClip(silent_wav(), "wav", 0.1)
    transcript = sarvam(handler).transcribe(clip, "kn")
    assert transcript.text == "ನಮಸ್ಕಾರ" and transcript.locale == "kn"
    assert transcript.provider == "sarvam"
    request = seen[0]
    assert request.url.path == "/speech-to-text"
    assert request.headers["api-subscription-key"] == KEY
    assert KEY not in str(request.url)
    body = request.content
    assert b'name="model"' in body and b"saaras:v4" in body
    assert b'name="language_code"' in body and b"kn-IN" in body
    assert b'filename="voice.wav"' in body


def test_sarvam_stt_without_hint_asks_for_auto_detection():
    seen: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.content)
        return httpx.Response(200, json={"transcript": "hello", "language_code": None})

    transcript = sarvam(handler).transcribe(AudioClip(silent_wav(), "wav"), None)
    assert b"unknown" in seen[0]
    assert transcript.locale is None


def test_sarvam_tts_request_and_reply():
    seen: list[httpx.Request] = []
    audio = silent_wav()

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"request_id": "r", "audios": [b64(audio)]})

    result = sarvam(handler).synthesize("ರುಕೋ ನಿಮ್ಮ ಪರವಾಗಿ.", "kn")
    assert result.data == audio and result.format == "wav" and result.provider == "sarvam"
    body = json.loads(seen[0].content)
    assert seen[0].url.path == "/text-to-speech"
    assert body == {
        "text": "ರುಕೋ ನಿಮ್ಮ ಪರವಾಗಿ.",
        "language_code": "kn-IN",
        "speaker": "shubh",
        "model": "bulbul:v3",
        "output_audio_codec": "wav",
    }


@pytest.mark.parametrize(
    ("text", "locale", "reason"),
    [
        ("x" * 51, "en", "text_length"),
        ("   ", "en", "text_length"),
        ("hello", "ta", "unsupported_locale"),
    ],
)
def test_sarvam_tts_rejects_before_calling(text, locale, reason):
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover - must not run
        raise AssertionError("no call expected")

    with pytest.raises(SpeechError) as info:
        sarvam(handler).synthesize(text, locale)
    assert info.value.reason == reason


def test_sarvam_retries_then_reports_typed_error_without_the_key():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(503, json={})

    provider = sarvam(handler, max_retries=1)
    with pytest.raises(SpeechError) as info:
        provider.synthesize("hello", "en")
    assert info.value.code == ErrorCode.SPEECH_UNAVAILABLE
    assert info.value.reason == "http_503" and len(calls) == 2
    assert KEY not in repr(provider) and KEY not in str(info.value)


@pytest.mark.parametrize("payload", [{"audios": []}, {"audios": ["%%%"]}, {}])
def test_sarvam_bad_tts_reply_is_an_error(payload):
    provider = sarvam(lambda request: httpx.Response(200, json=payload))
    with pytest.raises(SpeechError):
        provider.synthesize("hello", "en")


def test_sarvam_stt_missing_transcript_is_an_error():
    provider = sarvam(lambda request: httpx.Response(200, json={"language_code": "hi-IN"}))
    with pytest.raises(SpeechError):
        provider.transcribe(AudioClip(silent_wav(), "wav"), "hi")


# --- Fallback order -------------------------------------------------------------------


def test_chain_falls_back_to_the_next_provider():
    broken = FakeSpeechProvider(fail=True, name="first")
    working = FakeSpeechProvider("ನಮಸ್ಕಾರ", "kn", name="second")
    chain = SpeechChain([broken, working])
    assert chain.transcribe(AudioClip(silent_wav(), "wav"), "kn").provider == "second"
    assert chain.synthesize("hello", "en").provider == "second"
    assert chain.failures == ["first:fake_failure", "first:fake_failure"]


@pytest.mark.parametrize("providers", [[], [FakeSpeechProvider(fail=True)]])
def test_no_working_provider_is_speech_unavailable(providers):
    chain = SpeechChain(providers)
    with pytest.raises(RukoError) as info:
        chain.synthesize("hello", "en")
    assert info.value.code == ErrorCode.SPEECH_UNAVAILABLE


@pytest.mark.parametrize(
    ("names", "key", "expected"),
    [
        (["sarvam"], None, []),
        (["sarvam"], "k", ["sarvam"]),
        (["fake", "sarvam"], "k", ["fake", "sarvam"]),
        (["sarvam", "fake"], None, ["fake"]),
        (["bhashini", "fake"], "k", ["fake"]),
    ],
)
def test_chain_order_comes_from_settings(names, key, expected):
    settings = Settings(speech_providers=names, sarvam_api_key=SecretStr(key) if key else None)
    assert [p.name for p in build_speech_chain(settings).providers] == expected


# --- Speaking only Ruko's own templates -------------------------------------------------------


def test_speech_text_is_rendered_from_templates_in_the_locale():
    renderer = Renderer("kn")
    items = [
        TemplateRef(key="refusal.advice_request.message"),
        TemplateRef(key="refusal.alternative"),
    ]
    speech = build_speech_text(items, renderer, max_chars=2500)
    assert speech.item_count == 2 and not speech.truncated
    assert speech.text.startswith(renderer.text("refusal.advice_request.message"))


def test_speech_text_keeps_whole_items_within_the_limit():
    renderer = Renderer("en")
    first = renderer.text("refusal.advice_request.message")
    items = [
        TemplateRef(key="refusal.advice_request.message"),
        TemplateRef(key="refusal.alternative"),
    ]
    speech = build_speech_text(items, renderer, max_chars=len(first) + 5)
    assert speech.text == first and speech.item_count == 1 and speech.truncated


@pytest.mark.parametrize(
    "item",
    [
        TemplateRef(key="no.such.template"),
        TemplateRef(key="refusal.alternative", slots={"x": "BUY RELIANCE NOW"}),
        TemplateRef(key="refusal.alternative", slots={"x": "a"}),
    ],
)
def test_unknown_keys_and_wordy_slots_are_rejected(item):
    with pytest.raises(RukoError) as info:
        build_speech_text([item], Renderer("en"), max_chars=2500)
    assert info.value.code == ErrorCode.INVALID_REQUEST


FALLBACK = Template("output.blocked_fallback", "Safe text.", "draft")


def test_number_slots_are_allowed():
    store = TemplateStore(
        {
            "en": {
                "t": Template("t", "That is {amount}, about {pct} of savings.", "draft"),
                "output.blocked_fallback": FALLBACK,
            }
        }
    )
    item = TemplateRef(key="t", slots={"amount": "₹1,50,000", "pct": "12.5%"})
    speech = build_speech_text([item], Renderer("en", store=store), max_chars=2500)
    assert speech.text == "That is ₹1,50,000, about 12.5% of savings."


def test_missing_slot_is_rejected():
    store = TemplateStore(
        {
            "en": {
                "t": Template("t", "That is {amount}.", "draft"),
                "output.blocked_fallback": FALLBACK,
            }
        }
    )
    with pytest.raises(RukoError):
        build_speech_text([TemplateRef(key="t")], Renderer("en", store=store), max_chars=2500)


def test_speech_text_passes_the_output_filter():
    store = TemplateStore(
        {
            "en": {
                "bad": Template("bad", "Buy now, guaranteed returns!", "draft"),
                "output.blocked_fallback": Template(
                    "output.blocked_fallback", "Safe text.", "draft"
                ),
            }
        }
    )
    renderer = Renderer("en", store=store)
    speech = build_speech_text([TemplateRef(key="bad")], renderer, max_chars=2500)
    assert speech.text == "Safe text."
    assert renderer.blocked_count == 1


def test_speech_modules_never_store_audio():
    import inspect

    from ruko.language import speak
    from ruko.providers.speech import audio, factory, fake
    from ruko.providers.speech import sarvam as sarvam_module

    for module in (audio, sarvam_module, fake, factory, speak):
        source = inspect.getsource(module)
        assert "open(" not in source.replace("wave.open(", "")
        assert "write_bytes" not in source and "tempfile" not in source
