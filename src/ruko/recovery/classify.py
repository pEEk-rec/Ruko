"""Pick the recovery scenario from the user's answers (deterministic, data-driven).

The order lives in ``data/policy/recovery.yaml`` (``scenario_order``): the first answer
that is true decides the scenario; if none is, the scenario is ``no_loss_yet``.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from ruko.data_files import load_yaml
from ruko.models.recovery import RecoveryScenario
from ruko.models.requests import PaymentMethod, RecoveryAnswers


@dataclass(frozen=True)
class StepSpec:
    """One step definition."""

    id: str
    urgent: bool
    route: str | None
    payment_in: frozenset[PaymentMethod] | None
    if_installed_app: bool


@dataclass(frozen=True)
class ScenarioSpec:
    """Steps, evidence items and draft for one scenario."""

    steps: tuple[StepSpec, ...]
    evidence: tuple[str, ...]
    draft: str


@dataclass(frozen=True)
class RecoveryPolicy:
    """The recovery policy file."""

    version: str
    order: tuple[tuple[RecoveryScenario, str], ...]
    scenarios: dict[RecoveryScenario, ScenarioSpec]


def _step(raw: dict[str, Any]) -> StepSpec:
    payment_in = raw.get("payment_in")
    return StepSpec(
        id=raw["id"],
        urgent=bool(raw["urgent"]),
        route=raw.get("route"),
        payment_in=frozenset(PaymentMethod(p) for p in payment_in) if payment_in else None,
        if_installed_app=bool(raw.get("if_installed_app", False)),
    )


@lru_cache(maxsize=1)
def get_recovery_policy() -> RecoveryPolicy:
    """Load ``data/policy/recovery.yaml`` (cached)."""
    raw = load_yaml("policy", "recovery.yaml")
    return RecoveryPolicy(
        version=str(raw["version"]),
        order=tuple((RecoveryScenario(s), answer) for s, answer in raw["scenario_order"]),
        scenarios={
            RecoveryScenario(name): ScenarioSpec(
                steps=tuple(_step(s) for s in spec["steps"]),
                evidence=tuple(spec["evidence"]),
                draft=spec["draft"],
            )
            for name, spec in raw["scenarios"].items()
        },
    )


def classify(answers: RecoveryAnswers, policy: RecoveryPolicy | None = None) -> RecoveryScenario:
    """Return the scenario for the user's answers (first true answer in policy order)."""
    policy = policy or get_recovery_policy()
    for scenario, answer_field in policy.order:
        if getattr(answers, answer_field):
            return scenario
    return RecoveryScenario.NO_LOSS_YET
