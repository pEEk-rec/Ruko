"""Manual live check against the real Gemini API (synthetic messages only).

Never part of the main suite. Run with a key in ``.env``::

    .venv/Scripts/python -m pytest -m live tests/live -s
"""

from pathlib import Path

import pytest

from ruko.config import load_settings
from ruko.language.redact import redact
from ruko.models.common import ProductClass, ReasonCode
from ruko.providers.llm.gemini import GeminiProvider
from ruko.understanding.extract import extract
from ruko.understanding.merge import collect_deterministic, merge

pytestmark = pytest.mark.live

SYNTHETIC = {
    "en": (
        "Join our VIP group! BANKNIFTY 45000 CE, guaranteed 5% daily returns. Pay to 9876543210@ybl"
    ),
    "hi": "हमारे वीआईपी ग्रुप से जुड़ें। पक्का मुनाफा हर दिन, आज ही पैसे भेजें।",
    "kn": "ನಮ್ಮ ಗ್ರೂಪ್ ಸೇರಿ, ದಿನಕ್ಕೆ 2% ಖಚಿತ ಲಾಭ. ಇಂದು ಮಾತ್ರ!",
}


@pytest.fixture(scope="module")
def provider() -> GeminiProvider:
    settings = load_settings(dotenv_path=Path.cwd() / ".env")
    if settings.gemini_api_key is None:
        pytest.skip("no RUKO_GEMINI_API_KEY")
    return GeminiProvider.from_settings(settings)


@pytest.mark.parametrize("locale", sorted(SYNTHETIC))
def test_live_extraction(provider, locale):
    redacted = redact(SYNTHETIC[locale]).text
    outcome = extract(redacted, provider)
    assert outcome.mode == "llm", outcome.fallback_reason
    event = merge(collect_deterministic(redacted), outcome).event
    print(locale, outcome.attempts, outcome.extraction.product_class, sorted(event.signal_codes()))
    assert event.is_financial_decision
    assert ReasonCode.GUARANTEED_RETURN_CLAIM in event.signal_codes()
    if locale == "en":
        assert event.product_class == ProductClass.DERIVATIVE
