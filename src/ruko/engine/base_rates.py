"""Select the relevant group statistic from ``data/facts/base_rates.yaml``.

A base rate describes what happened to a *group* in a cited study. It is never a
prediction for this user, and it always travels with its source, ``as_of`` date,
verification status and a caveat.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from ruko.data_files import load_yaml
from ruko.models.common import SourceRef
from ruko.models.decision import BaseRateFact
from ruko.models.event import DecisionEvent
from ruko.models.profile import UserProfile

CAVEAT_DESCRIPTIVE = "base_rate.caveat_descriptive"
CAVEAT_GROUP = "base_rate.caveat_group"
TEXT_KEY_BY_SOURCE = {
    "sebi_eds_fy26": "base_rate.eds_loss_makers",
    "sebi_intraday_fy23": "base_rate.intraday_loss_makers",
}


@dataclass(frozen=True)
class Fact:
    """One fact record from the data file."""

    id: str
    source_key: str
    applies_to: dict[str, Any]
    group_key: str
    value: float
    year: str
    as_of: str
    verified_by_human: bool


@lru_cache(maxsize=1)
def load_base_rates() -> tuple[tuple[Fact, ...], dict[str, dict[str, Any]]]:
    """Load facts and their sources (cached)."""
    raw = load_yaml("facts", "base_rates.yaml")
    facts = tuple(
        Fact(
            id=f["id"],
            source_key=f["source"],
            applies_to=dict(f["applies_to"]),
            group_key=f["group_key"],
            value=float(f["value"]),
            year=str(f["year"]),
            as_of=str(f["as_of"]),
            verified_by_human=bool(f["verified_by_human"]),
        )
        for f in raw["facts"]
    )
    return facts, dict(raw["sources"])


def format_percent(value: float) -> str:
    """Format a percentage without trailing zeros: 87.70 -> '87.7', 71.0 -> '71'."""
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _applies(fact: Fact, event: DecisionEvent, age_band: str | None) -> bool:
    wanted = fact.applies_to
    if "product_class" not in wanted or wanted["product_class"] != event.product_class.value:
        return False
    if "holding_intent" in wanted and wanted["holding_intent"] != event.holding_intent.value:
        return False
    return wanted.get("age_band") in (None, age_band)


def select_base_rate(event: DecisionEvent, profile: UserProfile) -> BaseRateFact | None:
    """Pick the group statistic for this product class, preferring the user's age band.

    Args:
        event: The decision.
        profile: Device snapshot (only the optional age band is used).

    Returns:
        A ``BaseRateFact`` or None if no statistic applies.
    """
    facts, sources = load_base_rates()
    candidates = [f for f in facts if _applies(f, event, profile.age_band)]
    if not candidates:
        return None
    best = max(candidates, key=lambda f: f.applies_to.get("age_band") is not None)
    source = sources[best.source_key]
    return BaseRateFact(
        fact_id=best.id,
        group_key=best.group_key,
        text_key=TEXT_KEY_BY_SOURCE[best.source_key],
        slots={"pct": format_percent(best.value), "year": best.year},
        caveat_key=CAVEAT_DESCRIPTIVE if source.get("caveat_quote") else CAVEAT_GROUP,
        source=SourceRef(
            source_title=source["source_title"],
            source_url=source["source_url"],
            as_of=best.as_of,
            verified_by_human=best.verified_by_human,
        ),
    )
