"""Map Ruko locales (``kn``) to speech-provider language tags (``kn-IN``) and back.

The mapping lives in ``data/language/languages.yaml`` (``speech_code``), so adding a
spoken language is a data change.
"""

from __future__ import annotations

from functools import lru_cache

from ruko.data_files import load_yaml


@lru_cache(maxsize=1)
def _speech_codes() -> dict[str, str]:
    languages = load_yaml("language", "languages.yaml")["languages"]
    return {code: spec["speech_code"] for code, spec in languages.items() if "speech_code" in spec}


def speech_code_for(locale: str) -> str | None:
    """Return the BCP-47 speech tag for a locale, or None if it has no voice support."""
    return _speech_codes().get(locale)


def locale_for_speech_code(tag: str) -> str | None:
    """Return the Ruko locale for a provider's language tag, or None if unknown."""
    for locale, code in _speech_codes().items():
        if code.lower() == tag.lower():
            return locale
    return None
