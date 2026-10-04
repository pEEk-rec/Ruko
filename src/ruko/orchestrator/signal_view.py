"""Render one engine reason as a user-facing signal (shared by pause and content report)."""

from __future__ import annotations

from functools import lru_cache

from ruko.data_files import load_yaml
from ruko.engine.policy import get_intervention_policy
from ruko.language.templates import Renderer
from ruko.models.common import ReasonCode, dimension_of
from ruko.models.decision import Reason
from ruko.models.responses import SignalView, TemplateRef


@lru_cache(maxsize=1)
def signal_roles() -> dict[str, str]:
    """The role of every reason code (``data/policy/signal_roles.yaml``); behavioural is ``you``."""
    raw = load_yaml("policy", "signal_roles.yaml")
    mapping = {str(code): str(role) for code, role in raw["codes"].items()}
    for code in ReasonCode:
        if dimension_of(code).value == "behavioural":
            mapping[code.value] = "you"
    return mapping


def role_keys() -> set[str]:
    """Template keys of the role headings (for the template linter)."""
    return {f"signal.role.{role}" for role in load_yaml("policy", "signal_roles.yaml")["roles"]}


def render_signal(
    reason: Reason, renderer: Renderer, quote: str | None = None
) -> tuple[SignalView, list[TemplateRef]]:
    """Render a reason with its certainty label and severity tier.

    ``text`` keeps the original "Likely: …" form for compatibility; ``certainty_label`` and
    ``reason_text`` carry the two parts separately so a client can show the label as a badge
    in any locale without repeating it.

    Args:
        reason: One reason from the engine's decision.
        renderer: Renderer for the user's locale (applies the output filter).
        quote: The user's own words this signal rests on (see ``understanding.quotes``).

    Returns:
        The signal view and the template references for ``/v1/speak``.
    """
    label_key = f"certainty.{reason.certainty.value}"
    reason_key = f"reason.{reason.code.value.lower()}"
    label = renderer.text(label_key)
    body = renderer.text(reason_key)
    role = signal_roles()[reason.code.value]
    view = SignalView(
        role=role,
        role_label=renderer.text(f"signal.role.{role}"),
        code=reason.code,
        certainty=reason.certainty,
        severity=get_intervention_policy().severity(reason.code),
        text=f"{label}: {body}",
        certainty_label=label,
        reason_text=body,
        quote=quote,
    )
    return view, [TemplateRef(key=label_key), TemplateRef(key=reason_key)]
