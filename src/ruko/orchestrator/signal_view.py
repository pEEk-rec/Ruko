"""Render one engine reason as a user-facing signal (shared by pause and content report)."""

from __future__ import annotations

from ruko.engine.policy import get_intervention_policy
from ruko.language.templates import Renderer
from ruko.models.decision import Reason
from ruko.models.responses import SignalView, TemplateRef


def render_signal(reason: Reason, renderer: Renderer) -> tuple[SignalView, list[TemplateRef]]:
    """Render a reason with its certainty label and severity tier.

    ``text`` keeps the original "Likely: …" form for compatibility; ``certainty_label`` and
    ``reason_text`` carry the two parts separately so a client can show the label as a badge
    in any locale without repeating it.

    Args:
        reason: One reason from the engine's decision.
        renderer: Renderer for the user's locale (applies the output filter).

    Returns:
        The signal view and the template references for ``/v1/speak``.
    """
    label_key = f"certainty.{reason.certainty.value}"
    reason_key = f"reason.{reason.code.value.lower()}"
    label = renderer.text(label_key)
    body = renderer.text(reason_key)
    view = SignalView(
        code=reason.code,
        certainty=reason.certainty,
        severity=get_intervention_policy().severity(reason.code),
        text=f"{label}: {body}",
        certainty_label=label,
        reason_text=body,
    )
    return view, [TemplateRef(key=label_key), TemplateRef(key=reason_key)]
