"""The ``evaluate_content`` path: report what the message itself shows. No verdict.

Only the content dimension is used (the user is not making a decision here, so the
behavioural engine does not run on their profile). Each signal is shown with its
severity tier and certainty; safety-critical cards explain the strongest patterns; when
message signals alone reach the recovery threshold, the "already paid?" entry is added.
"""

from __future__ import annotations

from dataclasses import dataclass

from ruko.cards.catalog import get_catalog, resolve_fact
from ruko.cards.select import select_cards
from ruko.engine.engine import decide
from ruko.engine.policy import get_intervention_policy
from ruko.language.templates import Renderer
from ruko.models.common import InterventionLevel, dimension_of
from ruko.models.event import DecisionEvent
from ruko.models.profile import UserProfile
from ruko.models.responses import (
    ContentReportResponse,
    RecoveryEntry,
    ResponseMeta,
    SignalView,
    TemplateRef,
)

HEADLINE_KEY = "content.headline"
NO_SIGNALS_KEY = "content.no_signals"


@dataclass
class ContentReport:
    """Everything in a content report except the metadata."""

    fields: dict[str, object]
    speak: list[TemplateRef]
    unverified_fact_ids: list[str]

    def to_response(self, meta: ResponseMeta) -> ContentReportResponse:
        """Attach metadata and build the response model."""
        return ContentReportResponse.model_validate(
            {**self.fields, "speak": self.speak, "meta": meta}
        )


def build_content_report(
    event: DecisionEvent, renderer: Renderer, show_unverified: bool = True
) -> ContentReport:
    """Render the content report for a message.

    Args:
        event: The understood message (signals, source type, payment destination).
        renderer: Renderer for the user's locale.
        show_unverified: False in production: cards stating unverified facts are left out.

    Returns:
        The rendered report, speech references and unverified fact IDs.
    """
    content_only = event.model_copy(update={"is_financial_decision": False})
    profile = UserProfile()
    decision = decide(content_only, profile)
    policy = get_intervention_policy()
    speak = [TemplateRef(key=HEADLINE_KEY)]
    views: list[SignalView] = []
    for reason in decision.reasons:
        if dimension_of(reason.code).value != "content":
            continue
        label_key = f"certainty.{reason.certainty.value}"
        reason_key = f"reason.{reason.code.value.lower()}"
        text = f"{renderer.text(label_key)}: {renderer.text(reason_key)}"
        views.append(
            SignalView(
                code=reason.code,
                certainty=reason.certainty,
                severity=policy.severity(reason.code),
                text=text,
            )
        )
        speak += [TemplateRef(key=label_key), TemplateRef(key=reason_key)]
    note = None
    if not views:
        note = renderer.text(NO_SIGNALS_KEY)
        speak.append(TemplateRef(key=NO_SIGNALS_KEY))
    selection = select_cards(
        content_only,
        decision,
        profile,
        renderer,
        min_level=InterventionLevel.L0,
        show_unverified=show_unverified,
    )
    critical = [c for c in selection.cards if c.safety_critical]
    recovery = None
    if decision.recovery_entry:
        recovery = RecoveryEntry(text=renderer.text("pause.recovery_entry"))
        speak.append(TemplateRef(key="pause.recovery_entry"))
    fields: dict[str, object] = {
        "headline": renderer.text(HEADLINE_KEY),
        "signals": views,
        "note": note,
        "cards": critical,
        "recovery_entry": recovery,
    }
    specs = {card.id: card for card in get_catalog().cards}
    unverified = sorted(
        {
            fact_id
            for card in critical
            for fact_id in specs[card.id].facts
            if not resolve_fact(fact_id).source.verified_by_human
        }
    )
    return ContentReport(fields=fields, speak=speak, unverified_fact_ids=unverified)
