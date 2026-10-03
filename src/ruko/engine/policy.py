"""Loads ``data/policy/intervention.yaml`` into typed, immutable objects.

Also renders the policy as Markdown tables, so a test can check that
``docs/intervention_policy.md`` and ``docs/reason_codes.md`` say exactly what the YAML says.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from ruko.data_files import load_yaml
from ruko.models.common import (
    InterventionLevel,
    ProductClass,
    ReasonCode,
    Severity,
    dimension_of,
)


@dataclass(frozen=True)
class Band:
    """One profile band in rupees."""

    low: int
    high: int | None
    typical: int


@dataclass(frozen=True)
class CodePolicy:
    """Policy for one reason code."""

    severity: Severity
    category: str


@dataclass(frozen=True)
class LevelRule:
    """One level rule: when every set condition holds, the level is at least ``level``."""

    id: str
    level: InterventionLevel
    content_severity: Severity | None = None
    content_count: int = 0
    any_category: frozenset[str] = frozenset()
    count_categories: frozenset[str] = frozenset()
    count_in_categories: int = 0
    all_of_codes: frozenset[ReasonCode] = frozenset()
    behavioural_trigger: bool = False

    @property
    def uses_content(self) -> bool:
        """True if the rule looks at message signals."""
        return self.content_severity is not None

    @property
    def uses_behaviour(self) -> bool:
        """True if the rule looks at the user's context."""
        return bool(
            self.any_category
            or self.count_categories
            or self.all_of_codes
            or self.behavioural_trigger
        )


@dataclass(frozen=True)
class InterventionPolicy:
    """The whole intervention policy."""

    version: str
    expense_bands: dict[str, Band]
    savings_bands: dict[str, Band]
    codes: dict[ReasonCode, CodePolicy]
    level_rules: tuple[LevelRule, ...]
    l1_budget_per_week: int
    decay_streak_threshold: int
    l3_default_cooling_off_minutes: int
    plan_expected_for: frozenset[ProductClass]
    leveraged_product_classes: frozenset[ProductClass]
    high_frequency_bands: frozenset[str]
    adverse_move_illustrations_pct: tuple[float, ...]
    behavioural_trigger_categories: frozenset[str]
    recovery_min_content_level: InterventionLevel
    decay_categories: frozenset[str]
    raw_params: dict[str, Any]

    def severity(self, code: ReasonCode) -> Severity:
        """Return the severity tier of a code."""
        return self.codes[code].severity

    def category(self, code: ReasonCode) -> str:
        """Return the category of a code."""
        return self.codes[code].category

    def codes_in(self, categories: frozenset[str]) -> frozenset[ReasonCode]:
        """Return all codes whose category is in ``categories``."""
        return frozenset(c for c, p in self.codes.items() if p.category in categories)


def _bands(raw: dict[str, dict[str, Any]]) -> dict[str, Band]:
    return {
        name: Band(low=int(b["low"]), high=None if b["high"] is None else int(b["high"]),
                   typical=int(b["typical"]))
        for name, b in raw.items()
    }  # fmt: skip


def _rule(raw: dict[str, Any]) -> LevelRule:
    content = raw.get("content_at_least") or {}
    counted = raw.get("count_in_categories") or {}
    return LevelRule(
        id=raw["id"],
        level=InterventionLevel(raw["level"]),
        content_severity=Severity(content["severity"]) if content else None,
        content_count=int(content.get("count", 0)),
        any_category=frozenset(raw.get("any_category", [])),
        count_categories=frozenset(counted.get("categories", [])),
        count_in_categories=int(counted.get("count", 0)),
        all_of_codes=frozenset(ReasonCode(c) for c in raw.get("all_of_codes", [])),
        behavioural_trigger=bool(raw.get("behavioural_trigger", False)),
    )


def build_policy(raw: dict[str, Any]) -> InterventionPolicy:
    """Validate and convert a parsed intervention YAML document.

    Args:
        raw: Parsed YAML.

    Returns:
        The typed policy.

    Raises:
        ValueError: If a reason code is missing or a content code has a non-content category.
    """
    codes = {
        ReasonCode(name): CodePolicy(Severity(spec["severity"]), str(spec["category"]))
        for name, spec in raw["reason_codes"].items()
    }
    missing = set(ReasonCode) - set(codes)
    if missing:
        raise ValueError(f"intervention policy lacks codes: {sorted(missing)}")
    for code, spec in codes.items():
        if (spec.category == "content") != (dimension_of(code).value == "content"):
            raise ValueError(f"{code} category does not match its dimension")
    params = raw["params"]
    return InterventionPolicy(
        version=str(raw["version"]),
        expense_bands=_bands(raw["bands"]["monthly_expenses"]),
        savings_bands=_bands(raw["bands"]["liquid_savings"]),
        codes=codes,
        level_rules=tuple(_rule(r) for r in raw["level_rules"]),
        l1_budget_per_week=int(params["l1_budget_per_week"]),
        decay_streak_threshold=int(params["decay_streak_threshold"]),
        l3_default_cooling_off_minutes=int(params["l3_default_cooling_off_minutes"]),
        plan_expected_for=frozenset(ProductClass(p) for p in params["plan_expected_for"]),
        leveraged_product_classes=frozenset(
            ProductClass(p) for p in params["leveraged_product_classes"]
        ),
        high_frequency_bands=frozenset(str(b) for b in params["high_frequency_bands"]),
        adverse_move_illustrations_pct=tuple(
            float(p) for p in params["adverse_move_illustrations_pct"]
        ),
        behavioural_trigger_categories=frozenset(params["behavioural_trigger_categories"]),
        recovery_min_content_level=InterventionLevel(params["recovery_min_content_level"]),
        decay_categories=frozenset(params["decay_categories"]),
        raw_params=dict(params),
    )


@lru_cache(maxsize=1)
def get_intervention_policy() -> InterventionPolicy:
    """Return the intervention policy from the data directory (cached)."""
    return build_policy(load_yaml("policy", "intervention.yaml"))


def _param_value(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)


def describe_rule(rule: LevelRule) -> str:
    """Describe a level rule's conditions in plain words (used in the policy doc)."""
    parts = []
    if rule.content_severity is not None:
        noun = "content signal" if rule.content_count == 1 else "different content signals"
        parts.append(
            f"at least {rule.content_count} {noun} of severity "
            f"{rule.content_severity.value} or higher"
        )
    if rule.any_category:
        parts.append("a behavioural reason in: " + ", ".join(sorted(rule.any_category)))
    if rule.count_categories:
        parts.append(
            f"at least {rule.count_in_categories} reasons in: "
            + ", ".join(sorted(rule.count_categories))
        )
    if rule.all_of_codes:
        parts.append("all of: " + ", ".join(f"`{c.value}`" for c in sorted(rule.all_of_codes)))
    if rule.behavioural_trigger:
        parts.append("any behavioural trigger")
    return " AND ".join(parts)


def render_doc_tables(policy: InterventionPolicy) -> dict[str, str]:
    """Render the policy as the Markdown table rows used in the documents.

    Args:
        policy: The policy to render.

    Returns:
        A mapping from table name (``codes``, ``rules``, ``params``) to its rows.
    """
    codes = [
        f"| `{c.value}` | {dimension_of(c).value} | {p.severity.value} | {p.category} |"
        for c, p in policy.codes.items()
    ]
    rules = [f"| `{r.id}` | {describe_rule(r)} | {r.level.value} |" for r in policy.level_rules]
    shown = ["l1_budget_per_week", "decay_streak_threshold", "l3_default_cooling_off_minutes",
             "plan_expected_for", "leveraged_product_classes", "high_frequency_bands",
             "adverse_move_illustrations_pct", "behavioural_trigger_categories",
             "recovery_min_content_level", "decay_categories"]  # fmt: skip
    params = ["| Parameter | Value |", "|---|---|"]
    params += [f"| `{k}` | {_param_value(policy.raw_params[k])} |" for k in shown]
    return {"codes": "\n".join(codes), "rules": "\n".join(rules), "params": "\n".join(params)}
