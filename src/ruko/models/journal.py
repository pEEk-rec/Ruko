"""Journal entries. The journal lives on the device; the server only computes patterns."""

from __future__ import annotations

import datetime as dt
from enum import StrEnum

from pydantic import Field

from ruko.models.common import InterventionLevel, ProductClass, ReasonCode, SourceType, StrictModel


class JournalAction(StrEnum):
    """What the user did after the pause."""

    WENT_AHEAD = "went_ahead"
    WAITED = "waited"
    DROPPED = "dropped"


class JournalOutcome(StrEnum):
    """Outcome the user logged later (optional)."""

    GAIN = "gain"
    LOSS = "loss"
    FLAT = "flat"
    UNKNOWN = "unknown"


class JournalEntry(StrictModel):
    """One decision as recorded on the device."""

    id: str = Field(min_length=1, max_length=40, description="Device-generated entry ID.")
    date: dt.date = Field(description="Date of the decision.")
    product_class: ProductClass = Field(description="Product class.")
    amount_inr: int | None = Field(default=None, ge=1, description="Amount, if logged.")
    source_type: SourceType = Field(description="What prompted the decision.")
    level_shown: InterventionLevel = Field(description="Intervention level Ruko showed.")
    reason_codes: list[ReasonCode] = Field(default_factory=list, description="Reasons shown.")
    action: JournalAction = Field(description="What the user did.")
    overrode: bool = Field(
        default=False, description="True if the user continued past an L2/L3 intervention."
    )
    followed_own_rules: bool = Field(description="True if no personal rule was breached.")
    exit_plan_set: bool = Field(description="True if an exit plan was written.")
    exit_plan_followed: bool | None = Field(
        default=None, description="Logged later: was the exit plan followed? None = not yet."
    )
    outcome: JournalOutcome | None = Field(default=None, description="Logged later, optional.")
