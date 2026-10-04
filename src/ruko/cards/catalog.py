"""The card catalog (``data/cards/catalog.yaml``) and the facts cards cite.

A fact reference is ``"regulatory:<key>"`` (``data/facts/regulatory.yaml``) or
``"base_rates:<id>"`` (``data/facts/base_rates.yaml``). Resolving it gives the value
plus its source, ``as_of`` date and verification status, so a card can never show a
fact without its citation.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from ruko.data_files import load_yaml
from ruko.engine.base_rates import load_base_rates
from ruko.facts import investor_pages, regulatory
from ruko.models.common import (
    Action,
    HoldingIntent,
    InterventionLevel,
    ProductClass,
    ReasonCode,
    SourceRef,
)

NEEDS = frozenset({"adverse_moves", "base_rate", "recovery_entry", "amount"})
SLOT_BUILDERS = frozenset(
    {"none", "leverage_example", "base_rate", "fact_percent", "capital_gains"}
)


@dataclass(frozen=True)
class CardSpec:
    """One card definition."""

    id: str
    priority: int
    safety_critical: bool
    reason_codes_any: frozenset[ReasonCode]
    product_class_in: frozenset[ProductClass]
    holding_intent_in: frozenset[HoldingIntent]
    action_in: frozenset[Action]
    needs: frozenset[str]
    slots: str
    facts: tuple[str, ...]

    @property
    def title_key(self) -> str:
        """Template key of the title."""
        return f"card.{self.id}.title"

    @property
    def body_key(self) -> str:
        """Template key of the body."""
        return f"card.{self.id}.body"


@dataclass(frozen=True)
class CardCatalog:
    """All cards plus selection limits."""

    version: str
    pause_min_level: InterventionLevel
    max_cards: int
    cards: tuple[CardSpec, ...]

    def template_keys(self) -> set[str]:
        """Return every card template key (for the template linter)."""
        keys = {card.title_key for card in self.cards}
        return keys | {card.body_key for card in self.cards if card.slots != "base_rate"}


@dataclass(frozen=True)
class FactRef:
    """A resolved fact: its value and citation."""

    fact_id: str
    value: Any
    year: str | None
    source: SourceRef


def _card(raw: dict[str, Any]) -> CardSpec:
    when = raw.get("when") or {}
    spec = CardSpec(
        id=raw["id"],
        priority=int(raw["priority"]),
        safety_critical=bool(raw["safety_critical"]),
        reason_codes_any=frozenset(ReasonCode(c) for c in when.get("reason_codes_any", [])),
        product_class_in=frozenset(ProductClass(p) for p in when.get("product_class_in", [])),
        holding_intent_in=frozenset(HoldingIntent(h) for h in when.get("holding_intent_in", [])),
        action_in=frozenset(Action(a) for a in when.get("action_in", [])),
        needs=frozenset(when.get("needs", [])),
        slots=raw["slots"],
        facts=tuple(raw.get("facts") or ()),
    )
    if not spec.needs <= NEEDS or spec.slots not in SLOT_BUILDERS:
        raise ValueError(f"card {spec.id}: unknown 'needs' or 'slots'")
    return spec


@lru_cache(maxsize=1)
def get_catalog() -> CardCatalog:
    """Load and validate the card catalog (cached)."""
    raw = load_yaml("cards", "catalog.yaml")
    return CardCatalog(
        version=str(raw["version"]),
        pause_min_level=InterventionLevel(raw["pause_min_level"]),
        max_cards=int(raw["max_cards"]),
        cards=tuple(_card(c) for c in raw["cards"]),
    )


def resolve_fact(fact_id: str) -> FactRef:
    """Look up a fact reference and return it with its citation.

    Raises:
        KeyError: If the reference does not exist (a data-file bug, caught by tests).
    """
    kind, _, key = fact_id.partition(":")
    if kind in ("regulatory", "investor_pages"):
        entry = (regulatory() if kind == "regulatory" else investor_pages())[key]
        return FactRef(
            fact_id=fact_id,
            value=entry["value"],
            year=None,
            source=SourceRef(
                source_title=entry["source_title"],
                source_url=entry["source_url"],
                as_of=str(entry["as_of"]),
                verified_by_human=bool(entry["verified_by_human"]),
            ),
        )
    if kind == "base_rates":
        facts, sources = load_base_rates()
        fact = next(f for f in facts if f.id == key)
        source = sources[fact.source_key]
        return FactRef(
            fact_id=fact_id,
            value=fact.value,
            year=fact.year,
            source=SourceRef(
                source_title=source["source_title"],
                source_url=source["source_url"],
                as_of=fact.as_of,
                verified_by_human=fact.verified_by_human,
            ),
        )
    raise KeyError(fact_id)
