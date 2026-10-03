"""Manual live round-trip against Sarvam (TTS then STT) in Kannada and Hindi.

Never part of the main suite. Needs ``RUKO_SARVAM_API_KEY`` in ``.env``::

    .venv/Scripts/python -m pytest -m live tests/live/test_live_sarvam.py -s
"""

from pathlib import Path

import pytest

from ruko.config import load_settings
from ruko.language.speak import build_speech_text
from ruko.language.templates import Renderer
from ruko.models.responses import TemplateRef
from ruko.providers.speech.audio import decode_audio
from ruko.providers.speech.sarvam import SarvamProvider

pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def provider() -> SarvamProvider:
    settings = load_settings(dotenv_path=Path.cwd() / ".env")
    if settings.sarvam_api_key is None:
        pytest.skip("no RUKO_SARVAM_API_KEY")
    return SarvamProvider.from_settings(settings)


@pytest.mark.parametrize("locale", ["kn", "hi"])
def test_live_round_trip(provider, locale):
    import base64

    speech = build_speech_text(
        [TemplateRef(key="refusal.advice_request.message")], Renderer(locale), 2500
    )
    audio = provider.synthesize(speech.text, locale)
    clip = decode_audio(base64.b64encode(audio.data).decode(), "wav", 10_000_000, 60.0)
    transcript = provider.transcribe(clip, locale)
    print(locale, clip.duration_seconds, transcript.locale, len(transcript.text))
    assert transcript.text.strip()
    assert transcript.locale == locale
