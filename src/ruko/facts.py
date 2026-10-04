"""Accessors for facts in ``data/facts/regulatory.yaml`` and ``investor_pages.yaml``.

Code reads facts through these functions so every displayed or used fact has exactly
one home, with its source, ``as_of`` date and verification status.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from ruko.data_files import load_yaml


def regulatory() -> dict[str, Any]:
    """Return the parsed regulatory facts file."""
    return load_yaml("facts", "regulatory.yaml")


def investor_pages() -> dict[str, Any]:
    """Return SEBI investor-website topic pages linked from glossary entries."""
    return load_yaml("facts", "investor_pages.yaml")


@lru_cache(maxsize=1)
def upi_validated_handle() -> tuple[str, frozenset[str]]:
    """Return the ``@valid`` handle prefix and SEBI intermediary category suffixes."""
    value = regulatory()["upi_validated_handles"]["value"]
    return str(value["handle_prefix"]), frozenset(value["category_suffixes"])
