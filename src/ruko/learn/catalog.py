"""The lesson catalog (``data/learn/lessons.yaml``).

Each lesson is metadata only: when it applies, what it cites, how long it takes to read.
Its words live in the locale template files as ``lesson.<id>.*``.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from ruko.cards.catalog import resolve_fact
from ruko.data_files import load_yaml
from ruko.models.common import (
    Action,
    CalculatorTool,
    DecisionStage,
    InterventionLevel,
    ProductClass,
    ReasonCode,
)

NEEDS = frozenset({"amount", "leverage"})
SLOT_BUILDERS = frozenset({"none", "holding_months"})
TRIGGER_KEYS = frozenset(
    {"stage_in", "product_class_in", "action_in", "reason_codes_any", "calc_tool_in", "needs"}
)


@dataclass(frozen=True)
class Trigger:
    """One condition set. Every non-empty field must match; inside a field, any value."""

    stage_in: frozenset[DecisionStage] = frozenset()
    product_class_in: frozenset[ProductClass] = frozenset()
    action_in: frozenset[Action] = frozenset()
    reason_codes_any: frozenset[ReasonCode] = frozenset()
    calc_tool_in: frozenset[CalculatorTool] = frozenset()
    needs: frozenset[str] = frozenset()


@dataclass(frozen=True)
class LessonSpec:
    """One lesson definition."""

    id: str
    priority: int
    safety_critical: bool
    triggers: tuple[Trigger, ...]
    related_card: str | None
    related_tool: CalculatorTool | None
    amount_slot: bool
    slots: str
    facts: tuple[str, ...]
    read_seconds: int
    verified_by_human: bool
    as_of: str

    @property
    def title_key(self) -> str:
        """Template key of the title."""
        return f"lesson.{self.id}.title"

    @property
    def body_key(self) -> str:
        """Template key of the body without the user's numbers."""
        return f"lesson.{self.id}.body"

    @property
    def body_amount_key(self) -> str:
        """Template key of the body with the user's amount (only if ``amount_slot``)."""
        return f"lesson.{self.id}.body_amount"

    def template_keys(self) -> set[str]:
        """Return every template key this lesson needs."""
        keys = {self.title_key, self.body_key}
        return keys | {self.body_amount_key} if self.amount_slot else keys

    def visible(self, show_unverified: bool) -> bool:
        """True if the lesson may be shown (production needs text and facts verified)."""
        if show_unverified:
            return True
        facts_ok = all(resolve_fact(f).source.verified_by_human for f in self.facts)
        return self.verified_by_human and facts_ok


@dataclass(frozen=True)
class LessonCatalog:
    """All lessons plus the selection limits."""

    version: str
    max_lessons: int
    max_explanation_items: int
    pause_min_level: InterventionLevel
    lessons: tuple[LessonSpec, ...]

    def get(self, lesson_id: str) -> LessonSpec | None:
        """Return the lesson with this ID, or None."""
        return next((lesson for lesson in self.lessons if lesson.id == lesson_id), None)

    def template_keys(self) -> set[str]:
        """Return every lesson template key (for the template linter)."""
        return set().union(*(lesson.template_keys() for lesson in self.lessons))


def _trigger(raw: dict[str, Any]) -> Trigger:
    unknown = set(raw) - TRIGGER_KEYS
    needs = frozenset(raw.get("needs", []))
    if unknown or not needs <= NEEDS:
        raise ValueError(f"unknown trigger keys or needs: {sorted(unknown | (needs - NEEDS))}")
    return Trigger(
        stage_in=frozenset(DecisionStage(v) for v in raw.get("stage_in", [])),
        product_class_in=frozenset(ProductClass(v) for v in raw.get("product_class_in", [])),
        action_in=frozenset(Action(v) for v in raw.get("action_in", [])),
        reason_codes_any=frozenset(ReasonCode(v) for v in raw.get("reason_codes_any", [])),
        calc_tool_in=frozenset(CalculatorTool(v) for v in raw.get("calc_tool_in", [])),
        needs=needs,
    )


def _lesson(raw: dict[str, Any]) -> LessonSpec:
    spec = LessonSpec(
        id=raw["id"],
        priority=int(raw["priority"]),
        safety_critical=bool(raw["safety_critical"]),
        triggers=tuple(_trigger(t) for t in raw["triggers"]),
        related_card=raw.get("related_card"),
        related_tool=CalculatorTool(raw["related_tool"]) if raw.get("related_tool") else None,
        amount_slot=bool(raw.get("amount_slot", False)),
        slots=raw.get("slots", "none"),
        facts=tuple(raw.get("facts") or ()),
        read_seconds=int(raw["read_seconds"]),
        verified_by_human=bool(raw["verified_by_human"]),
        as_of=str(raw["as_of"]),
    )
    if spec.slots not in SLOT_BUILDERS or not spec.triggers:
        raise ValueError(f"lesson {spec.id}: unknown slots or no triggers")
    return spec


@lru_cache(maxsize=1)
def get_lesson_catalog() -> LessonCatalog:
    """Load and validate the lesson catalog (cached)."""
    raw = load_yaml("learn", "lessons.yaml")
    return LessonCatalog(
        version=str(raw["version"]),
        max_lessons=int(raw["max_lessons"]),
        max_explanation_items=int(raw["max_explanation_items"]),
        pause_min_level=InterventionLevel(raw["pause_min_level"]),
        lessons=tuple(_lesson(item) for item in raw["lessons"]),
    )
