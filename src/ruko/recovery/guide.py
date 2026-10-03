"""Build the recovery guide: ordered steps (urgent first), evidence checklist, draft text.

Contacts come only from ``data/facts/recovery_routes.yaml`` (with sources). Every text is
a template rendered through the output filter. Ruko never submits anything: the draft
complaint has blanks the user fills in and sends themselves, and Ruko never asks for an
OTP, PIN, password or account number.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from ruko.data_files import load_yaml
from ruko.language.templates import Renderer
from ruko.models.common import SourceRef
from ruko.models.recovery import RecoveryGuide, RecoveryScenario, RecoveryStep
from ruko.models.requests import RecoveryAnswers
from ruko.models.responses import ResponseMeta, TemplateRef
from ruko.recovery.classify import RecoveryPolicy, StepSpec, classify, get_recovery_policy

NO_PROMISE_KEY = "recovery.no_promise"


@lru_cache(maxsize=1)
def recovery_routes() -> dict[str, dict[str, Any]]:
    """Load the official routes (cached)."""
    return dict(load_yaml("facts", "recovery_routes.yaml")["routes"])


def _route_source(route: dict[str, Any]) -> SourceRef:
    return SourceRef(
        source_title=route["source_title"],
        source_url=route["source_url"],
        as_of=str(route["as_of"]),
        verified_by_human=bool(route["verified_by_human"]),
    )


def _included(step: StepSpec, answers: RecoveryAnswers) -> bool:
    if step.payment_in is not None and answers.payment_method not in step.payment_in:
        return False
    return not (step.if_installed_app and not answers.installed_app)


def ordered_steps(
    scenario: RecoveryScenario, answers: RecoveryAnswers, policy: RecoveryPolicy | None = None
) -> list[StepSpec]:
    """Return the scenario's applicable steps, urgent ones first (stable order otherwise)."""
    policy = policy or get_recovery_policy()
    steps = [s for s in policy.scenarios[scenario].steps if _included(s, answers)]
    return sorted(steps, key=lambda s: not s.urgent)


def build_guide(answers: RecoveryAnswers, renderer: Renderer, meta: ResponseMeta) -> RecoveryGuide:
    """Build the full recovery guide for the user's answers.

    Args:
        answers: Scenario answers (yes/no and payment method only; no personal data).
        renderer: Renderer for the user's locale (runs the output filter).
        meta: Response metadata to attach.

    Returns:
        The ``RecoveryGuide`` with steps, evidence checklist, draft complaint and sources.
    """
    policy = get_recovery_policy()
    scenario = classify(answers, policy)
    spec = policy.scenarios[scenario]
    routes = recovery_routes()
    steps: list[RecoveryStep] = []
    sources: list[SourceRef] = []
    speak = [TemplateRef(key=NO_PROMISE_KEY)]
    for order, step in enumerate(ordered_steps(scenario, answers, policy), start=1):
        route = routes[step.route] if step.route else None
        key = f"recovery.step.{step.id}"
        steps.append(
            RecoveryStep(
                order=order,
                urgent=step.urgent,
                text=renderer.text(key),
                route_id=step.route,
                contact=route["contact"] if route else None,
            )
        )
        speak.append(TemplateRef(key=key))
        if route and _route_source(route) not in sources:
            sources.append(_route_source(route))
    return RecoveryGuide(
        scenario=scenario,
        steps=steps,
        evidence_checklist=[renderer.text(f"recovery.evidence.{e}") for e in spec.evidence],
        draft_complaint=renderer.text(f"recovery.draft.{spec.draft}"),
        sources=sources,
        speak=speak,
        meta=meta,
    )
