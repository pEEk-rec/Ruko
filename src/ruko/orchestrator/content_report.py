"""The ``evaluate_content`` path: report what the message itself shows. No verdict.

Only the content dimension is used (the user is not making a decision here, so the
behavioural engine does not run on their profile). Each signal is shown with its
severity tier and certainty; safety-critical cards explain the strongest patterns; when
message signals alone reach the recovery threshold, the "already paid?" entry is added.
"""

from __future__ import annotations

from dataclasses import dataclass

from ruko.engine.engine import decide
from ruko.language.templates import Renderer
from ruko.learn.hub import Focus, suggest_lesson
from ruko.learn.select import explain_decision
from ruko.models.common import DecisionStage, InterventionLevel, ReasonCode, dimension_of
from ruko.models.event import DecisionEvent
from ruko.models.profile import UserProfile
from ruko.models.responses import (
    ContentReportResponse,
    RecoveryEntry,
    ResponseMeta,
    SignalView,
    TemplateRef,
)
from ruko.orchestrator.signal_view import render_signal

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
    event: DecisionEvent,
    renderer: Renderer,
    show_unverified: bool = True,
    quotes: dict[ReasonCode, str] | None = None,
    profile: UserProfile | None = None,
) -> ContentReport:
    """Render the content report for a message.

    Args:
        event: The understood message (signals, source type, payment destination).
        renderer: Renderer for the user's locale.
        show_unverified: False in production: cards stating unverified facts are left out.
        quotes: The user's own words behind each signal (``understanding.quotes``).
        profile: Device snapshot, used only to pick a lesson worth reading next.

    Returns:
        The rendered report, speech references and unverified fact IDs.
    """
    content_only = event.model_copy(update={"is_financial_decision": False})
    profile = UserProfile()
    decision = decide(content_only, profile)
    speak = [TemplateRef(key=HEADLINE_KEY)]
    views: list[SignalView] = []
    for reason in decision.reasons:
        if dimension_of(reason.code).value != "content":
            continue
        view, refs = render_signal(reason, renderer, (quotes or {}).get(reason.code))
        views.append(view)
        speak += refs
    note = None
    if not views:
        note = renderer.text(NO_SIGNALS_KEY)
        speak.append(TemplateRef(key=NO_SIGNALS_KEY))
    explained = explain_decision(
        content_only,
        decision,
        profile,
        renderer,
        card_min_level=InterventionLevel.L0,
        lesson_min_level=InterventionLevel.L0,
        critical_only=True,
        show_unverified=show_unverified,
    )
    recovery = None
    if decision.recovery_entry:
        recovery = RecoveryEntry(text=renderer.text("pause.recovery_entry"))
        speak.append(TemplateRef(key="pause.recovery_entry"))
    fields: dict[str, object] = {
        "headline": renderer.text(HEADLINE_KEY),
        "signals": views,
        "note": note,
        "cards": explained.cards.cards,
        "lessons": explained.lessons,
        "learn_next": None
        if explained.lessons
        else suggest_lesson(
            profile or UserProfile(),
            renderer,
            focus=Focus(stages=frozenset({DecisionStage.EVALUATE_CONTENT})),
            show_unverified=show_unverified,
        ),
        "recovery_entry": recovery,
    }
    return ContentReport(
        fields=fields, speak=speak, unverified_fact_ids=sorted(explained.unverified_fact_ids)
    )
