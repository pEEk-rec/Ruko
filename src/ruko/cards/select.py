"""Deterministic card selection: which 0-3 cards explain this decision.

Rules:

1. A card applies when all its ``when`` conditions match the event and the decision.
2. Cards the device reports as seen are left out, unless they are safety-critical.
3. Highest priority first; at most ``max_cards`` (3).
4. On the pause screen, cards appear only from ``pause_min_level`` (L2) up.

Numbers in cards are the user's own (from the engine) or cited facts; every text goes
through the ``Renderer`` (output filter). No card recommends anything.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ruko.cards.catalog import CardCatalog, CardSpec, FactRef, get_catalog, resolve_fact
from ruko.engine.base_rates import format_percent
from ruko.language.numbers import rupees
from ruko.language.templates import Renderer
from ruko.models.common import InterventionLevel
from ruko.models.decision import InterventionDecision
from ruko.models.event import DecisionEvent
from ruko.models.profile import UserProfile
from ruko.models.responses import ExplanationCard, TemplateRef


@dataclass
class CardSelection:
    """Selected cards, what to read aloud, and which shown facts are unverified."""

    cards: list[ExplanationCard] = field(default_factory=list)
    speak: list[TemplateRef] = field(default_factory=list)
    unverified_fact_ids: list[str] = field(default_factory=list)


def _needs_met(card: CardSpec, event: DecisionEvent, decision: InterventionDecision) -> bool:
    available = {
        "adverse_moves": bool(decision.numbers.adverse_moves),
        "base_rate": decision.base_rate is not None,
        "recovery_entry": decision.recovery_entry,
        "amount": event.amount_inr is not None,
    }
    return all(available[need] for need in card.needs)


def card_applies(card: CardSpec, event: DecisionEvent, decision: InterventionDecision) -> bool:
    """Return True if every condition of the card matches this decision."""
    codes = set(decision.reason_codes)
    if card.reason_codes_any and not card.reason_codes_any & codes:
        return False
    if card.product_class_in and event.product_class not in card.product_class_in:
        return False
    if card.holding_intent_in and event.holding_intent not in card.holding_intent_in:
        return False
    return _needs_met(card, event, decision)


def matching_cards(
    event: DecisionEvent,
    decision: InterventionDecision,
    profile: UserProfile,
    catalog: CardCatalog | None = None,
) -> list[CardSpec]:
    """Return the cards to show, in order, after fading and the max-cards cut."""
    catalog = catalog or get_catalog()
    seen = set(profile.seen_card_ids)
    candidates = [
        card
        for card in catalog.cards
        if card_applies(card, event, decision) and (card.safety_critical or card.id not in seen)
    ]
    candidates.sort(key=lambda c: -c.priority)  # stable: catalog order breaks ties
    return candidates[: catalog.max_cards]


def _slots(card: CardSpec, decision: InterventionDecision, facts: list[FactRef]) -> dict[str, str]:
    if card.slots == "leverage_example":
        move = decision.numbers.adverse_moves[0]
        return {
            "amount": rupees(move.exposure_inr),
            "pct": format_percent(move.move_pct),
            "loss": rupees(move.loss_inr),
        }
    if card.slots == "fact_percent":
        return {"pct": format_percent(float(facts[0].value)), "year": facts[0].year or ""}
    if card.slots == "capital_gains":
        value = facts[0].value
        return {
            "months": str(value["long_term_holding_months"]),
            "stcg": format_percent(float(value["short_term_rate_pct"])),
            "ltcg": format_percent(float(value["long_term_rate_pct"])),
            "exempt": rupees(int(value["long_term_exempt_up_to_inr"])),
            "as_of": str(value["effective_for_transfers_from"]),
        }
    return {}


def _render(
    card: CardSpec, decision: InterventionDecision, renderer: Renderer
) -> tuple[ExplanationCard, list[TemplateRef], list[str]]:
    facts = [resolve_fact(f) for f in card.facts]
    sources = [f.source for f in facts]
    fact_ids = [f.fact_id for f in facts]
    title = TemplateRef(key=card.title_key)
    if card.slots == "base_rate" and decision.base_rate is not None:
        rate = decision.base_rate
        body_refs = [
            TemplateRef(key=rate.text_key, slots=rate.slots),
            TemplateRef(key=f"base_rate.group.{rate.group_key}"),
            TemplateRef(key=rate.caveat_key),
        ]
        sources.append(rate.source)
        fact_ids.append(f"base_rates:{rate.fact_id}")
    else:
        body_refs = [TemplateRef(key=card.body_key, slots=_slots(card, decision, facts))]
    body = " ".join(renderer.text(ref.key, **ref.slots) for ref in body_refs)
    explanation = ExplanationCard(
        id=card.id,
        title=renderer.text(title.key),
        body=body,
        safety_critical=card.safety_critical,
        as_of=min((s.as_of for s in sources), default=None),
        sources=sources,
        verified_by_human=bool(sources) and all(s.verified_by_human for s in sources),
    )
    unverified = [fid for fid, s in zip(fact_ids, sources, strict=True) if not s.verified_by_human]
    return explanation, [title, *body_refs], unverified


def select_cards(
    event: DecisionEvent,
    decision: InterventionDecision,
    profile: UserProfile,
    renderer: Renderer,
    *,
    min_level: InterventionLevel | None = None,
    catalog: CardCatalog | None = None,
) -> CardSelection:
    """Select and render the cards for one decision.

    Args:
        event: The decision event.
        decision: The engine's decision (reasons, numbers, base rate, recovery flag).
        profile: Device snapshot (seen card IDs).
        renderer: Renderer for the user's locale.
        min_level: Lowest level that shows cards (defaults to the catalog's pause level).
        catalog: Optional catalog override.

    Returns:
        Rendered cards (max 3), speech references and unverified fact IDs.
    """
    catalog = catalog or get_catalog()
    threshold = min_level or catalog.pause_min_level
    selection = CardSelection()
    if decision.level.rank < threshold.rank:
        return selection
    for card in matching_cards(event, decision, profile, catalog):
        explanation, refs, unverified = _render(card, decision, renderer)
        selection.cards.append(explanation)
        selection.speak.extend(refs)
        for fact_id in unverified:
            if fact_id not in selection.unverified_fact_ids:
                selection.unverified_fact_ids.append(fact_id)
    return selection
