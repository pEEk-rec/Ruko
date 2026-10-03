"""Loading of the YAML data files (policy, lexicons, templates, cards, facts).

Data files are read once and cached. They are configuration, not code: changing a
threshold, a template or a lexicon pattern never needs a code change.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from ruko.config import get_settings


def data_dir() -> Path:
    """Return the configured data directory."""
    return get_settings().data_dir


@lru_cache(maxsize=128)
def _load_yaml_cached(path: str) -> Any:
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_yaml(*parts: str) -> Any:
    """Load (and cache) a YAML file under the data directory.

    Args:
        *parts: Path parts relative to the data directory, e.g. ``("policy", "guardrails.yaml")``.

    Returns:
        The parsed YAML content.
    """
    return _load_yaml_cached(str(data_dir().joinpath(*parts)))


def clear_cache() -> None:
    """Forget cached files (used by tests that point at another data directory)."""
    _load_yaml_cached.cache_clear()
