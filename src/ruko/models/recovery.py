"""After-harm recovery contracts. Ruko drafts; the user sends. Nothing is submitted for them."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field

from ruko.models.common import SourceRef, StrictModel
from ruko.models.responses import ResponseMeta, TemplateRef


class RecoveryScenario(StrEnum):
    """What went wrong, chosen deterministically from the user's answers."""

    PAID_SCAMMER = "paid_scammer"
    SUSPICIOUS_APP_INSTALLED = "suspicious_app_installed"
    REGISTERED_BROKER_ISSUE = "registered_broker_issue"
    UNAUTHORIZED_TRADE = "unauthorized_trade"
    CANNOT_WITHDRAW = "cannot_withdraw"


class RecoveryStep(StrictModel):
    """One step, in order. Urgent steps come first."""

    order: int = Field(ge=1, description="Position in the list, starting at 1.")
    urgent: bool = Field(description="True for time-critical steps (e.g. call 1930 now).")
    text: str = Field(description="Rendered instruction.")
    route_id: str | None = Field(
        default=None, description="Route ID in data/facts/recovery_routes.yaml."
    )
    contact: str | None = Field(
        default=None, description="Phone number or official URL from the routes file."
    )


class RecoveryGuide(StrictModel):
    """Ordered steps, an evidence checklist and a draft complaint for the user to send."""

    kind: Literal["recovery"] = "recovery"
    scenario: RecoveryScenario = Field(description="Selected scenario.")
    steps: list[RecoveryStep] = Field(min_length=1, description="Ordered steps.")
    evidence_checklist: list[str] = Field(description="Rendered items to collect.")
    draft_complaint: str = Field(description="Rendered draft text. The user copies and sends it.")
    sources: list[SourceRef] = Field(default_factory=list, description="Citations for routes.")
    speak: list[TemplateRef] = Field(
        default_factory=list, description="What /v1/speak should read aloud."
    )
    meta: ResponseMeta = Field(description="Metadata.")
