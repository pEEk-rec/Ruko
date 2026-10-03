"""Schema validation and JSON round-trip tests for every data contract."""

import datetime as dt

import pytest
from pydantic import BaseModel, ValidationError

from ruko.models import (
    AttentionState,
    Certainty,
    ClarifyQuestion,
    ClarifyResponse,
    DecisionEvent,
    EvidenceSpan,
    ExplanationCard,
    FundingSource,
    InterventionDecision,
    InterventionLevel,
    JournalEntry,
    NormalizedInput,
    PauseResponse,
    PlannedDecision,
    ProductClass,
    RawInput,
    Reason,
    ReasonCode,
    RecoveryGuide,
    RecoveryScenario,
    RecoveryStep,
    RefusalClass,
    RefusalResponse,
    ResponseMeta,
    Severity,
    Signal,
    SignalSource,
    SourceRef,
    UserProfile,
)


def _meta() -> ResponseMeta:
    return ResponseMeta(request_id="req-12345678", locale="en")


def _decision() -> InterventionDecision:
    return InterventionDecision(
        level=InterventionLevel.L2,
        computed_level=InterventionLevel.L2,
        reasons=[
            Reason(
                code=ReasonCode.BORROWED_FUNDS,
                severity=Severity.HIGH,
                certainty=Certainty.LIKELY,
                source=SignalSource.USER,
            )
        ],
        attention=AttentionState(
            l1_budget_per_week=3, l1_used_this_week=0, suppressed_by_budget=False
        ),
        policy_version="1",
    )


def _examples() -> list[BaseModel]:
    event = DecisionEvent(
        is_financial_decision=True,
        product_class=ProductClass.DERIVATIVE,
        amount_inr=20000,
        funding_source=FundingSource.BORROWED,
        signals=[
            Signal(
                code=ReasonCode.URGENCY_PRESSURE,
                certainty=Certainty.POSSIBLE,
                source=SignalSource.LEXICON,
                evidence=EvidenceSpan(start=0, end=9, text="Hurry up!"),
            )
        ],
        field_confidence={"product_class": Certainty.LIKELY},
    )
    return [
        RawInput(type="text", content="Buy this now", claimed_locale="hi"),
        NormalizedInput(
            text="call [PHONE]",
            language="en",
            script="latin",
            language_confidence=0.9,
            is_code_mixed=False,
            is_romanized=False,
            redaction_counts={"phone": 1},
        ),
        event,
        UserProfile(
            monthly_expenses_band="25k_50k",
            liquid_savings_band="1l_3l",
            experience={ProductClass.DERIVATIVE: "none"},
            plans=[
                PlannedDecision(
                    id="p1", product_class="mutual_fund", amount_min_inr=1000, amount_max_inr=5000
                )
            ],
        ),
        _decision(),
        PauseResponse(
            level=InterventionLevel.L2,
            headline="Pause",
            override_label="Continue anyway",
            decision=_decision(),
            cards=[ExplanationCard(id="c1", title="t", body="b")],
            meta=_meta(),
        ),
        RefusalResponse(
            refusal_class=RefusalClass.ADVICE_REQUEST, message="m", alternative="a", meta=_meta()
        ),
        ClarifyResponse(
            questions=[ClarifyQuestion(field="amount_inr", text="How much?")],
            event=event,
            meta=_meta(),
        ),
        JournalEntry(
            id="j1",
            date=dt.date(2026, 9, 1),
            product_class="cash_equity",
            source_type="own_research",
            level_shown="L0",
            action="went_ahead",
            followed_own_rules=True,
            exit_plan_set=True,
        ),
        RecoveryGuide(
            scenario=RecoveryScenario.PAID_SCAMMER,
            steps=[RecoveryStep(order=1, urgent=True, text="Call 1930")],
            evidence_checklist=["Transaction ID"],
            draft_complaint="draft",
            sources=[SourceRef(source_title="t", source_url="https://x", as_of="2026-01-01")],
            meta=_meta(),
        ),
    ]


@pytest.mark.parametrize("model", _examples(), ids=lambda m: type(m).__name__)
def test_json_round_trip(model):
    restored = type(model).model_validate_json(model.model_dump_json())
    assert restored == model


def test_unknown_fields_are_rejected():
    with pytest.raises(ValidationError):
        RawInput(type="text", content="x", surprise=True)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"type": "fax", "content": "x"},
        {"type": "text", "content": ""},
        {"type": "text", "content": "x", "claimed_locale": "English"},
    ],
)
def test_raw_input_invalid(kwargs):
    with pytest.raises(ValidationError):
        RawInput(**kwargs)


@pytest.mark.parametrize("amount", [0, -5, 1.5, "lots"])
def test_amount_must_be_positive_integer_rupees(amount):
    with pytest.raises(ValidationError):
        DecisionEvent(is_financial_decision=True, amount_inr=amount)


def test_protected_goal_id_requires_goal_funding():
    with pytest.raises(ValidationError):
        DecisionEvent(is_financial_decision=True, protected_goal_id="g1", funding_source="savings")
    DecisionEvent(
        is_financial_decision=True, protected_goal_id="g1", funding_source="protected_goal"
    )


def test_signal_certainty_has_no_binary_verdict():
    assert {c.value for c in Certainty} == {"possible", "likely", "unclear"}
    with pytest.raises(ValidationError):
        Signal(code=ReasonCode.URGENCY_PRESSURE, certainty="certain", source="lexicon")


def test_override_is_always_allowed():
    with pytest.raises(ValidationError):
        InterventionDecision(**{**_decision().model_dump(), "override_allowed": False})


def test_profile_rejects_bad_bands_and_rules():
    with pytest.raises(ValidationError):
        UserProfile(monthly_expenses_band="huge")
    with pytest.raises(ValidationError):
        UserProfile(rules={"max_share_of_savings_pct": 150})
    with pytest.raises(ValidationError):
        PlannedDecision(id="p", product_class="ipo", amount_min_inr=10, amount_max_inr=5)


def test_pause_response_allows_at_most_three_cards():
    cards = [ExplanationCard(id=f"c{i}", title="t", body="b") for i in range(4)]
    with pytest.raises(ValidationError):
        PauseResponse(
            level="L1",
            headline="h",
            override_label="o",
            decision=_decision(),
            cards=cards,
            meta=_meta(),
        )


def test_clarify_needs_at_least_one_question():
    with pytest.raises(ValidationError):
        ClarifyResponse(questions=[], event=DecisionEvent(is_financial_decision=True), meta=_meta())


def test_level_and_severity_ranks_are_ordered():
    assert [lvl.rank for lvl in InterventionLevel] == [0, 1, 2, 3]
    assert [s.rank for s in Severity] == [0, 1, 2, 3]


def test_reason_code_catalogue_is_complete():
    required = {
        "RULE_MAX_SHARE_EXCEEDED", "RULE_MAX_AMOUNT_EXCEEDED", "BORROWED_FUNDS",
        "PROTECTED_GOAL_FUNDS", "EMERGENCY_BUFFER_AT_RISK", "FIRST_TIME_PRODUCT",
        "LEVERAGED_PRODUCT", "NO_EXIT_PLAN", "PLAN_DEVIATION", "UNSOLICITED_SOURCE",
        "GUARANTEED_RETURN_CLAIM", "URGENCY_PRESSURE", "AUTHORITY_CLAIM",
        "PROFIT_SCREENSHOT_SOCIAL_PROOF", "PAY_TO_INDIVIDUAL_ACCOUNT", "UNVERIFIED_PLATFORM_LINK",
        "IMPERSONATION_SUSPECTED", "APP_INSTALL_REQUEST", "WITHDRAWAL_FEE_DEMAND",
        "POST_LOSS_REENTRY_DECLARED", "HIGH_FREQUENCY_DECLARED",
    }  # fmt: skip
    assert {code.value for code in ReasonCode} == required
