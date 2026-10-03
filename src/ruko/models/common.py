"""Shared enums and small value types used across all data contracts.

Money convention: every amount is an **integer number of rupees** (``int``), never a
float and never paise. Retail decisions are typed by users in whole rupees, and
integers make every comparison and test exact.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

LOCALE_PATTERN = r"^[a-z]{2,3}$"
"""Locales are short ISO 639 codes (``en``, ``hi``, ``kn``). Which ones are enabled is
configuration, so adding a language is a data task, not a code change."""


class StrictModel(BaseModel):
    """Base for all contracts: unknown fields are rejected, values validated on assignment."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Certainty(StrEnum):
    """How sure Ruko is about a signal or field. There is deliberately no 'certain'."""

    POSSIBLE = "possible"
    LIKELY = "likely"
    UNCLEAR = "unclear"


class SignalSource(StrEnum):
    """Which component produced a signal."""

    LEXICON = "lexicon"
    LLM = "llm"
    RULE = "rule"
    USER = "user"


class ProductClass(StrEnum):
    """Broad class of what the user is about to put money into."""

    CASH_EQUITY = "cash_equity"
    DERIVATIVE = "derivative"
    IPO = "ipo"
    MUTUAL_FUND = "mutual_fund"
    SCHEME_OR_APP = "scheme_or_app"
    CRYPTO = "crypto"
    UNKNOWN = "unknown"


class FundingSource(StrEnum):
    """Where the money for this decision comes from. Always declared by the user."""

    SAVINGS = "savings"
    BORROWED = "borrowed"
    EMERGENCY_FUND = "emergency_fund"
    PROTECTED_GOAL = "protected_goal"
    UNKNOWN = "unknown"


class SourceType(StrEnum):
    """Who or what prompted the decision."""

    UNSOLICITED_GROUP = "unsolicited_group"
    KNOWN_PERSON = "known_person"
    INFLUENCER = "influencer"
    OWN_RESEARCH = "own_research"
    UNKNOWN = "unknown"


class PaymentDestination(StrEnum):
    """Where money would be sent, if the message says."""

    BROKER_OR_EXCHANGE = "broker_or_exchange"
    INDIVIDUAL_ACCOUNT = "individual_account"
    UNKNOWN = "unknown"


class HoldingIntent(StrEnum):
    """How long the user means to hold (used for cost and tax cards only)."""

    INTRADAY = "intraday"
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    UNKNOWN = "unknown"


class InterventionLevel(StrEnum):
    """How much friction Ruko adds. Every level is overridable by the user."""

    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"

    @property
    def rank(self) -> int:
        """Return 0..3 so levels can be compared numerically."""
        return int(self.value[1])


class Severity(StrEnum):
    """Default weight of a reason code."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        """Return 0..3 so severities can be compared numerically."""
        return ["low", "medium", "high", "critical"].index(self.value)


class ReasonCode(StrEnum):
    """Every reason Ruko can give for an intervention (see docs/reason_codes.md)."""

    RULE_MAX_SHARE_EXCEEDED = "RULE_MAX_SHARE_EXCEEDED"
    RULE_MAX_AMOUNT_EXCEEDED = "RULE_MAX_AMOUNT_EXCEEDED"
    BORROWED_FUNDS = "BORROWED_FUNDS"
    PROTECTED_GOAL_FUNDS = "PROTECTED_GOAL_FUNDS"
    EMERGENCY_BUFFER_AT_RISK = "EMERGENCY_BUFFER_AT_RISK"
    FIRST_TIME_PRODUCT = "FIRST_TIME_PRODUCT"
    LEVERAGED_PRODUCT = "LEVERAGED_PRODUCT"
    NO_EXIT_PLAN = "NO_EXIT_PLAN"
    PLAN_DEVIATION = "PLAN_DEVIATION"
    UNSOLICITED_SOURCE = "UNSOLICITED_SOURCE"
    GUARANTEED_RETURN_CLAIM = "GUARANTEED_RETURN_CLAIM"
    URGENCY_PRESSURE = "URGENCY_PRESSURE"
    AUTHORITY_CLAIM = "AUTHORITY_CLAIM"
    PROFIT_SCREENSHOT_SOCIAL_PROOF = "PROFIT_SCREENSHOT_SOCIAL_PROOF"
    PAY_TO_INDIVIDUAL_ACCOUNT = "PAY_TO_INDIVIDUAL_ACCOUNT"
    UNVERIFIED_PLATFORM_LINK = "UNVERIFIED_PLATFORM_LINK"
    IMPERSONATION_SUSPECTED = "IMPERSONATION_SUSPECTED"
    APP_INSTALL_REQUEST = "APP_INSTALL_REQUEST"
    WITHDRAWAL_FEE_DEMAND = "WITHDRAWAL_FEE_DEMAND"
    POST_LOSS_REENTRY_DECLARED = "POST_LOSS_REENTRY_DECLARED"
    HIGH_FREQUENCY_DECLARED = "HIGH_FREQUENCY_DECLARED"


class RefusalClass(StrEnum):
    """Inputs Ruko refuses to process, with a fixed localized response."""

    ADVICE_REQUEST = "ADVICE_REQUEST"
    PREDICTION_REQUEST = "PREDICTION_REQUEST"
    INSTRUMENT_EVALUATION = "INSTRUMENT_EVALUATION"
    BROKER_RECOMMENDATION = "BROKER_RECOMMENDATION"
    ROLEPLAY_ADVISOR = "ROLEPLAY_ADVISOR"
    SENSITIVE_DATA_SUBMISSION = "SENSITIVE_DATA_SUBMISSION"


class EvidenceSpan(StrictModel):
    """A span of the (already redacted) input that supports a signal."""

    start: int = Field(ge=0, description="Start offset (characters) in the redacted text.")
    end: int = Field(ge=0, description="End offset (exclusive) in the redacted text.")
    text: str = Field(max_length=200, description="The matched excerpt, already redacted.")


class SourceRef(StrictModel):
    """A citation for a displayed fact."""

    source_title: str = Field(description="Title of the primary source document or page.")
    source_url: str = Field(description="URL of the primary source.")
    as_of: str = Field(description="Date the fact is valid as of (YYYY-MM-DD).")
    verified_by_human: bool = Field(
        default=False, description="True only after the repo owner has checked the source."
    )
