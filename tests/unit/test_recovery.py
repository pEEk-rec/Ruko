"""Stage 9: recovery routing (scenarios, urgent-first ordering, routes, drafts, filter)."""

import inspect

import pytest

from ruko.guardrails.output_filter import find_violations
from ruko.language.templates import Renderer
from ruko.models.recovery import RecoveryScenario as S
from ruko.models.requests import PaymentMethod as P
from ruko.models.requests import RecoveryAnswers
from ruko.models.responses import ResponseMeta
from ruko.recovery import classify as classify_module
from ruko.recovery import guide as guide_module
from ruko.recovery.classify import classify, get_recovery_policy
from ruko.recovery.guide import build_guide, recovery_routes


def answers(**fields) -> RecoveryAnswers:
    return RecoveryAnswers.model_validate({"paid_money": False, **fields})


def guide(locale: str = "en", **fields):
    meta = ResponseMeta(request_id="test-request", locale=locale)
    return build_guide(answers(**fields), Renderer(locale), meta)


@pytest.mark.parametrize(
    ("fields", "scenario"),
    [
        ({"paid_money": True, "payment_method": "upi"}, S.PAID_SCAMMER),
        ({"paid_money": True, "cannot_withdraw": True}, S.CANNOT_WITHDRAW),
        ({"installed_app": True}, S.SUSPICIOUS_APP_INSTALLED),
        ({"paid_money": True, "installed_app": True}, S.PAID_SCAMMER),
        ({"registered_broker_involved": True}, S.REGISTERED_BROKER_ISSUE),
        ({"registered_broker_involved": True, "unauthorized_trade": True}, S.UNAUTHORIZED_TRADE),
        ({"unauthorized_trade": True}, S.UNAUTHORIZED_TRADE),
        ({}, S.NO_LOSS_YET),
    ],
)
def test_scenario_routing(fields, scenario):
    assert classify(answers(**fields)) == scenario


def test_every_scenario_has_a_policy():
    assert set(get_recovery_policy().scenarios) == set(S)


@pytest.mark.parametrize("locale", ["en", "hi", "kn"])
@pytest.mark.parametrize(
    "fields",
    [
        {"paid_money": True, "payment_method": "upi"},
        {"paid_money": True, "payment_method": "cash_or_other", "installed_app": True},
        {"paid_money": True, "cannot_withdraw": True, "payment_method": "bank_transfer"},
        {"installed_app": True},
        {"registered_broker_involved": True},
        {"unauthorized_trade": True},
        {},
    ],
)
def test_urgent_steps_always_come_first(locale, fields):
    result = guide(locale, **fields)
    flags = [step.urgent for step in result.steps]
    assert flags == sorted(flags, reverse=True)
    assert [step.order for step in result.steps] == list(range(1, len(result.steps) + 1))


def test_upi_fraud_calls_1930_then_the_bank_first():
    result = guide(paid_money=True, payment_method=P.UPI)
    assert [s.route_id for s in result.steps[:2]] == ["helpline_1930", "bank"]
    assert result.steps[0].urgent and result.steps[0].contact == "1930"
    assert result.steps[1].contact is None  # each bank's own number


def test_bank_step_only_when_money_moved_through_a_bank():
    result = guide(paid_money=True, payment_method=P.CASH_OR_OTHER)
    assert "bank" not in [s.route_id for s in result.steps]


def test_app_removal_only_when_an_app_was_installed():
    without_app = guide(paid_money=True, payment_method=P.UPI)
    with_app = guide(paid_money=True, payment_method=P.UPI, installed_app=True)
    assert len(with_app.steps) == len(without_app.steps) + 1
    assert any("Uninstall" in s.text for s in with_app.steps if s.urgent)


def test_cannot_withdraw_says_stop_paying():
    result = guide(paid_money=True, cannot_withdraw=True, payment_method=P.UPI)
    assert any("Don't pay anything more" in s.text for s in result.steps)


def test_broker_issue_goes_entity_first_then_scores_then_odr():
    result = guide(registered_broker_involved=True)
    routes = [s.route_id for s in result.steps if s.route_id]
    assert routes == ["broker_grievance", "sebi_scores", "smart_odr"]
    assert result.steps[1].contact == "https://scores.sebi.gov.in"


def test_contacts_come_only_from_the_routes_file_with_sources():
    contacts = {r["contact"] for r in recovery_routes().values()}
    for fields in ({"paid_money": True, "payment_method": "upi"}, {"unauthorized_trade": True}):
        result = guide(**fields)
        assert {s.contact for s in result.steps} <= contacts | {None}
        assert result.sources and all(not s.verified_by_human for s in result.sources)


def test_every_route_has_a_source_and_as_of():
    for route in recovery_routes().values():
        assert route["source_url"].startswith("https://")
        assert route["as_of"] and route["verified_by_human"] is False


def test_draft_is_for_the_user_to_send_and_holds_no_user_data():
    result = guide(paid_money=True, payment_method=P.UPI)
    assert "[transaction ID]" in result.draft_complaint
    assert "[date]" in result.draft_complaint
    assert len(result.evidence_checklist) >= 5


@pytest.mark.parametrize("locale", ["en", "hi", "kn"])
def test_all_recovery_text_passes_the_filter(locale):
    for fields in ({"paid_money": True, "payment_method": "card", "installed_app": True},
                   {"registered_broker_involved": True}, {}):  # fmt: skip
        renderer = Renderer(locale)
        result = build_guide(
            answers(**fields), renderer, ResponseMeta(request_id="t", locale=locale)
        )
        texts = (
            [s.text for s in result.steps] + result.evidence_checklist + [result.draft_complaint]
        )
        assert renderer.blocked_count == 0 and renderer.missing_keys == []
        assert all(not find_violations(t) for t in texts)
        assert result.speak[0].key == "recovery.no_promise"


def test_recovery_never_submits_or_asks_for_secrets():
    for module in (classify_module, guide_module):
        source = inspect.getsource(module)
        for banned in ("httpx", "urllib", "smtplib", "requests.post"):
            assert banned not in source
    fields = set(RecoveryAnswers.model_fields)
    assert not fields & {"otp", "pin", "password", "account_number", "card_number", "upi_id"}
