"""Loads ``data/policy/intervention.yaml`` into typed, immutable objects.

Also renders the policy as Markdown tables, so a test can check that
``docs/intervention_policy.md`` says exactly what the YAML says.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from ruko.data_files import load_yaml
from ruko.models.common import InterventionLevel, ProductClass, ReasonCode, Severity


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
    solo_level: InterventionLevel
    category: str


@dataclass(frozen=True)
class Combination:
    """A combination rule: at least ``min_count`` of ``codes`` present gives ``level``."""

    id: str
    level: InterventionLevel
    min_count: int
    codes: tuple[ReasonCode, ...]


@dataclass(frozen=True)
class InterventionPolicy:
    """The whole intervention policy."""

    version: str
    expense_bands: dict[str, Band]
    savings_bands: dict[str, Band]
    codes: dict[ReasonCode, CodePolicy]
    combinations: tuple[Combination, ...]
    l1_budget_per_week: int
    decay_streak_threshold: int
    l3_default_cooling_off_minutes: int
    exit_plan_required_for: frozenset[ProductClass]
    leveraged_product_classes: frozenset[ProductClass]
    high_frequency_bands: frozenset[str]
    adverse_move_illustrations_pct: tuple[float, ...]
    recovery_categories: frozenset[str]
    decay_categories: frozenset[str]
    raw_params: dict[str, Any]

    def severity(self, code: ReasonCode) -> Severity:
        """Return the default severity of a code."""
        return self.codes[code].severity

    def codes_in(self, categories: frozenset[str]) -> frozenset[ReasonCode]:
        """Return all codes whose category is in ``categories``."""
        return frozenset(c for c, p in self.codes.items() if p.category in categories)


def _bands(raw: dict[str, dict[str, Any]]) -> dict[str, Band]:
    return {
        name: Band(low=int(b["low"]), high=None if b["high"] is None else int(b["high"]),
                   typical=int(b["typical"]))
        for name, b in raw.items()
    }  # fmt: skip


def build_policy(raw: dict[str, Any]) -> InterventionPolicy:
    """Validate and convert a parsed intervention YAML document.

    Args:
        raw: Parsed YAML.

    Returns:
        The typed policy.

    Raises:
        ValueError: If a reason code is missing from the policy.
    """
    codes = {
        ReasonCode(name): CodePolicy(
            severity=Severity(spec["severity"]),
            solo_level=InterventionLevel(spec["solo_level"]),
            category=str(spec["category"]),
        )
        for name, spec in raw["reason_codes"].items()
    }
    missing = set(ReasonCode) - set(codes)
    if missing:
        raise ValueError(f"intervention policy lacks codes: {sorted(missing)}")
    params = raw["params"]
    return InterventionPolicy(
        version=str(raw["version"]),
        expense_bands=_bands(raw["bands"]["monthly_expenses"]),
        savings_bands=_bands(raw["bands"]["liquid_savings"]),
        codes=codes,
        combinations=tuple(
            Combination(
                id=c["id"],
                level=InterventionLevel(c["level"]),
                min_count=int(c["min_count"]),
                codes=tuple(ReasonCode(x) for x in c["of"]),
            )
            for c in raw["combinations"]
        ),
        l1_budget_per_week=int(params["l1_budget_per_week"]),
        decay_streak_threshold=int(params["decay_streak_threshold"]),
        l3_default_cooling_off_minutes=int(params["l3_default_cooling_off_minutes"]),
        exit_plan_required_for=frozenset(ProductClass(p) for p in params["exit_plan_required_for"]),
        leveraged_product_classes=frozenset(
            ProductClass(p) for p in params["leveraged_product_classes"]
        ),
        high_frequency_bands=frozenset(str(b) for b in params["high_frequency_bands"]),
        adverse_move_illustrations_pct=tuple(
            float(p) for p in params["adverse_move_illustrations_pct"]
        ),
        recovery_categories=frozenset(params["recovery_categories"]),
        decay_categories=frozenset(params["decay_categories"]),
        raw_params=dict(params),
    )


@lru_cache(maxsize=1)
def get_intervention_policy() -> InterventionPolicy:
    """Return the intervention policy from the data directory (cached)."""
    return build_policy(load_yaml("policy", "intervention.yaml"))


def _param_value(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(v).rstrip("0").rstrip(".") if isinstance(v, float) else str(v)
                         for v in value)  # fmt: skip
    return str(value)


def render_doc_tables(policy: InterventionPolicy) -> dict[str, str]:
    """Render the policy as the Markdown table rows used in the policy document.

    Args:
        policy: The policy to render.

    Returns:
        A mapping from table name (``solo``, ``combo``, ``params``) to its rows.
    """
    solo = [f"| `{c.value}` | {p.severity.value} | {p.solo_level.value} |"
            for c, p in policy.codes.items()]  # fmt: skip
    combo = []
    for rule in policy.combinations:
        names = ", ".join(f"`{c.value}`" for c in rule.codes)
        when = (f"all of: {names}" if rule.min_count == len(rule.codes)
                else f"at least {rule.min_count} of: {names}")  # fmt: skip
        combo.append(f"| `{rule.id}` | {when} | {rule.level.value} |")
    shown = ["l1_budget_per_week", "decay_streak_threshold", "l3_default_cooling_off_minutes",
             "exit_plan_required_for", "leveraged_product_classes", "high_frequency_bands",
             "adverse_move_illustrations_pct"]  # fmt: skip
    params = ["| Parameter | Value |", "|---|---|"]
    params += [f"| `{k}` | {_param_value(policy.raw_params[k])} |" for k in shown]
    return {"solo": "\n".join(solo), "combo": "\n".join(combo), "params": "\n".join(params)}
