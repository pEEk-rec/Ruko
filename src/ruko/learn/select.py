"""Deterministic lesson selection: which 0-2 lessons explain this decision.

Rules (data in ``data/learn/lessons.yaml``):

1. A lesson applies when any of its trigger sets matches the decision.
2. Lessons the device reports as seen fade out, unless they are safety-critical.
3. In production, a lesson is shown only if its text and every fact it cites are verified.
4. Safety-critical lessons first, then by priority; at most ``max_lessons`` (2).
5. Cards and lessons share one budget of ``max_explanation_items`` (3). A chosen lesson
   replaces its ``related_card`` (same topic once). If the budget is still exceeded,
   non-critical lessons go first, then non-critical cards, then the lowest lesson.

No lesson is written by the LLM, recommends a product or compares products; every text is
rendered through the ``Renderer`` (output validator, response type ``lesson``).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ruko.cards.catalog import CardSpec, get_catalog, resolve_fact
from ruko.cards.select import CardSelection, matching_cards, render_cards
from ruko.language.numbers import rupees
from ruko.language.templates import Renderer
from ruko.learn.catalog import LessonCatalog, LessonSpec, Trigger, get_lesson_catalog
from ruko.models.calculation import CalculationInputs
from ruko.models.common import (
    Action,
    CalculatorTool,
    DecisionStage,
    InterventionLevel,
    ProductClass,
    ReasonCode,
)
from ruko.models.decision import InterventionDecision
from ruko.models.event import DecisionEvent
from ruko.models.profile import UserProfile
from ruko.models.responses import Lesson, TemplateRef


@dataclass(frozen=True)
class LessonContext:
    """The features of a decision (or calculation) that lessons are chosen by."""

    stage: DecisionStage | None = None
    product_class: ProductClass | None = None
    action: Action | None = None
    reason_codes: frozenset[ReasonCode] = frozenset()
    calc_tool: CalculatorTool | None = None
    amount_inr: int | None = None
    leverage: bool = False

    @classmethod
    def for_decision(cls, event: DecisionEvent, decision: InterventionDecision) -> LessonContext:
        """Context for a pause or content report."""
        return cls(
            stage=event.stage,
            product_class=event.product_class,
            action=event.action,
            reason_codes=frozenset(decision.reason_codes),
            amount_inr=event.amount_inr,
            leverage=ReasonCode.LEVERAGED_PRODUCT in decision.reason_codes,
        )

    @classmethod
    def for_calculation(cls, inputs: CalculationInputs) -> LessonContext:
        """Context for a calculation; the amount is the one the lesson's sentence names."""
        amount = {
            CalculatorTool.SIP: inputs.monthly_inr,
            CalculatorTool.CONSEQUENCE: inputs.amount_inr,
        }.get(inputs.tool) if inputs.tool else None  # fmt: skip
        return cls(
            stage=DecisionStage.CALCULATE,
            calc_tool=inputs.tool,
            amount_inr=amount,
            leverage=(inputs.leverage or 1) > 1,
        )


def trigger_matches(trigger: Trigger, ctx: LessonContext) -> bool:
    """Return True if every condition of one trigger set holds."""
    checks = (
        (trigger.stage_in, ctx.stage in trigger.stage_in),
        (trigger.product_class_in, ctx.product_class in trigger.product_class_in),
        (trigger.action_in, ctx.action in trigger.action_in),
        (trigger.reason_codes_any, bool(trigger.reason_codes_any & ctx.reason_codes)),
        (trigger.calc_tool_in, ctx.calc_tool in trigger.calc_tool_in),
    )
    if not all(ok for condition, ok in checks if condition):
        return False
    available = {"amount": ctx.amount_inr is not None, "leverage": ctx.leverage}
    return all(available[need] for need in trigger.needs)


def lesson_applies(lesson: LessonSpec, ctx: LessonContext) -> bool:
    """Return True if any trigger set of the lesson matches."""
    return any(trigger_matches(t, ctx) for t in lesson.triggers)


def matching_lessons(
    ctx: LessonContext,
    profile: UserProfile,
    catalog: LessonCatalog | None = None,
    *,
    show_unverified: bool = True,
) -> list[LessonSpec]:
    """Return applicable lessons after fading and visibility: critical first, then priority."""
    catalog = catalog or get_lesson_catalog()
    seen = set(profile.seen_lesson_ids)
    found = [
        lesson
        for lesson in catalog.lessons
        if lesson_applies(lesson, ctx)
        and (lesson.safety_critical or lesson.id not in seen)
        and lesson.visible(show_unverified)
    ]
    found.sort(key=lambda lesson: (not lesson.safety_critical, -lesson.priority))
    return found[: catalog.max_lessons]


def plan_explanations(
    cards: list[CardSpec],
    lessons: list[LessonSpec],
    catalog: LessonCatalog | None = None,
    max_cards: int | None = None,
) -> tuple[list[CardSpec], list[LessonSpec]]:
    """Fit cards and lessons into one budget (see the module rules 4 and 5).

    Cards and lessons are ranked together: safety-critical first, then by priority, a
    lesson ahead of a card of equal priority. Walking that order, an item is taken while
    budget remains; a card is skipped when a lesson already taken is about the same
    topic, and a lesson takes the place of its ``related_card`` if that card came first.

    Args:
        cards: Applicable cards in priority order (not yet capped).
        lessons: Applicable lessons in selection order.
        catalog: Lesson catalog (limits).
        max_cards: Card cap (defaults to the card catalog's ``max_cards``).

    Returns:
        The cards and lessons to show, each in the order they were taken.
    """
    catalog = catalog or get_lesson_catalog()
    max_cards = max_cards if max_cards is not None else get_catalog().max_cards
    ranked: list[tuple[bool, int, int, CardSpec | LessonSpec]] = [
        (not x.safety_critical, -x.priority, 0, x) for x in lessons[: catalog.max_lessons]
    ] + [(not x.safety_critical, -x.priority, 1, x) for x in cards]
    ranked.sort(key=lambda item: item[:3])
    taken_cards: list[CardSpec] = []
    taken_lessons: list[LessonSpec] = []
    for *_, item in ranked:
        room = len(taken_cards) + len(taken_lessons) < catalog.max_explanation_items
        if isinstance(item, LessonSpec):
            swap = next((c for c in taken_cards if c.id == item.related_card), None)
            if swap is not None:  # same topic: the lesson replaces its shorter card
                taken_cards.remove(swap)
                taken_lessons.append(item)
            elif room:
                taken_lessons.append(item)
        elif (
            room
            and len(taken_cards) < max_cards
            and not any(x.related_card == item.id for x in taken_lessons)
        ):
            taken_cards.append(item)
    return taken_cards, taken_lessons


def _slots(lesson: LessonSpec) -> dict[str, str]:
    if lesson.slots == "holding_months":
        value = resolve_fact(lesson.facts[0]).value
        return {"months": str(value["long_term_holding_months"])}
    return {}


def render_lesson(
    lesson: LessonSpec, renderer: Renderer, amount_inr: int | None = None
) -> tuple[Lesson, list[str]]:
    """Render one lesson in the renderer's locale.

    Args:
        lesson: The lesson definition.
        renderer: Renderer for the user's locale (runs the output validator).
        amount_inr: The user's own amount; used only if the lesson has an amount version.

    Returns:
        The rendered lesson and the IDs of its unverified facts.
    """
    slots = _slots(lesson)
    body_key = lesson.body_key
    if lesson.amount_slot and amount_inr is not None:
        body_key = lesson.body_amount_key
        slots = {**slots, "amount": rupees(amount_inr)}
    facts = [resolve_fact(f) for f in lesson.facts]
    sources = [f.source for f in facts]
    refs = [TemplateRef(key=lesson.title_key), TemplateRef(key=body_key, slots=slots)]
    rendered = Lesson(
        id=lesson.id,
        title=renderer.text(lesson.title_key),
        body=renderer.text(body_key, **slots),
        read_seconds=lesson.read_seconds,
        safety_critical=lesson.safety_critical,
        own_guidance=lesson.own_guidance,
        related_tool=lesson.related_tool,
        as_of=lesson.as_of,
        sources=sources,
        verified_by_human=lesson.verified_by_human and all(s.verified_by_human for s in sources),
        speak=refs,
    )
    unverified = [f.fact_id for f in facts if not f.source.verified_by_human]
    return rendered, unverified


@dataclass
class Explanations:
    """Cards and lessons for one response, with speech refs and unverified fact IDs."""

    cards: CardSelection = field(default_factory=CardSelection)
    lessons: list[Lesson] = field(default_factory=list)
    unverified_fact_ids: list[str] = field(default_factory=list)

    def add_unverified(self, fact_ids: list[str]) -> None:
        """Record unverified fact IDs once each, in order."""
        for fact_id in fact_ids:
            if fact_id not in self.unverified_fact_ids:
                self.unverified_fact_ids.append(fact_id)


def _render_all(
    cards: list[CardSpec],
    lessons: list[LessonSpec],
    decision: InterventionDecision | None,
    renderer: Renderer,
    amount_inr: int | None,
) -> Explanations:
    result = Explanations()
    if cards and decision is not None:
        result.cards = render_cards(cards, decision, renderer)
        result.add_unverified(result.cards.unverified_fact_ids)
    for spec in lessons:
        lesson, unverified = render_lesson(spec, renderer, amount_inr)
        result.lessons.append(lesson)
        result.add_unverified(unverified)
    return result


def explain_decision(
    event: DecisionEvent,
    decision: InterventionDecision,
    profile: UserProfile,
    renderer: Renderer,
    *,
    card_min_level: InterventionLevel | None = None,
    lesson_min_level: InterventionLevel | None = None,
    critical_only: bool = False,
    show_unverified: bool = True,
) -> Explanations:
    """Choose and render the cards and lessons for a pause or a content report.

    Args:
        event: The decision event.
        decision: The engine's decision.
        profile: Device snapshot (seen cards and lessons).
        renderer: Renderer for the user's locale.
        card_min_level: Lowest level that shows cards (default: the card catalog's).
        lesson_min_level: Lowest level that shows lessons (default: the lesson catalog's).
        critical_only: Content report: only safety-critical cards and lessons.
        show_unverified: False in production.

    Returns:
        Rendered cards (max 3) and lessons (max 2), together at most 3.
    """
    card_threshold = card_min_level or get_catalog().pause_min_level
    lesson_threshold = lesson_min_level or get_lesson_catalog().pause_min_level
    cards: list[CardSpec] = []
    if decision.level.rank >= card_threshold.rank:
        cards = matching_cards(
            event, decision, profile, show_unverified=show_unverified, capped=False
        )
        if critical_only:
            cards = [card for card in cards if card.safety_critical]
    lessons: list[LessonSpec] = []
    if decision.level.rank >= lesson_threshold.rank:
        ctx = LessonContext.for_decision(event, decision)
        lessons = matching_lessons(ctx, profile, show_unverified=show_unverified)
        if critical_only:
            lessons = [lesson for lesson in lessons if lesson.safety_critical]
    kept_cards, kept_lessons = plan_explanations(cards, lessons)
    return _render_all(kept_cards, kept_lessons, decision, renderer, event.amount_inr)


def explain_calculation(
    inputs: CalculationInputs,
    profile: UserProfile,
    renderer: Renderer,
    *,
    show_unverified: bool = True,
) -> Explanations:
    """Choose and render the lessons for a calculation (calculations have no cards)."""
    ctx = LessonContext.for_calculation(inputs)
    lessons = matching_lessons(ctx, profile, show_unverified=show_unverified)
    _, kept = plan_explanations([], lessons)
    return _render_all([], kept, None, renderer, ctx.amount_inr)


def speak_refs_for_lesson(lesson_id: str, *, show_unverified: bool = True) -> list[TemplateRef]:
    """Return the speech references for a lesson ID (title and plain body).

    Raises:
        KeyError: Unknown lesson, or a lesson hidden in this environment.
    """
    lesson = get_lesson_catalog().get(lesson_id)
    if lesson is None or not lesson.visible(show_unverified):
        raise KeyError(lesson_id)
    return [
        TemplateRef(key=lesson.title_key),
        TemplateRef(key=lesson.body_key, slots=_slots(lesson)),
    ]
