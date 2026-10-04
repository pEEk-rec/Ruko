"""The verification flags in data/facts, and what verified facts mean for production."""

import json
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from ruko.config import Settings
from ruko.main import create_app

FACTS = Path(__file__).resolve().parents[2] / "data" / "facts"
OPEN_TODO = {"regulatory:capital_gains_listed_equity", "regulatory:sebi_investor_website"}


def entries() -> dict[str, dict]:
    """Every fact entry as ``file:key`` -> its dict (placeholders in charges.yaml excluded)."""
    found: dict[str, dict] = {}
    for name in ("regulatory", "investor_pages"):
        for key, entry in yaml.safe_load((FACTS / f"{name}.yaml").read_text("utf-8")).items():
            found[f"{name}:{key}"] = entry
    routes = yaml.safe_load((FACTS / "recovery_routes.yaml").read_text("utf-8"))["routes"]
    found.update({f"recovery_routes:{k}": v for k, v in routes.items()})
    base = yaml.safe_load((FACTS / "base_rates.yaml").read_text("utf-8"))
    found.update({f"base_rates:{f['id']}": f for f in base["facts"]})
    return found


def test_every_fact_has_a_boolean_flag_and_a_source():
    for fact_id, entry in entries().items():
        assert isinstance(entry["verified_by_human"], bool), fact_id


def test_a_fact_with_an_open_todo_verify_is_never_marked_verified():
    for fact_id, entry in entries().items():
        has_todo = "todo_verify" in entry or "TODO_VERIFY" in json.dumps(entry, default=str)
        if has_todo:
            assert entry["verified_by_human"] is False, fact_id


def test_only_the_two_facts_with_open_todo_items_are_still_unverified():
    unverified = {k for k, v in entries().items() if not v["verified_by_human"]}
    assert unverified == OPEN_TODO


def test_placeholder_charges_are_never_marked_verified_without_a_value():
    charges = yaml.safe_load((FACTS / "charges.yaml").read_text("utf-8"))
    text = json.dumps(charges, default=str)
    assert "TODO_VERIFY" in text  # still placeholders: unused
    for key, entry in charges.items():
        if isinstance(entry, dict) and entry.get("value") == "TODO_VERIFY":
            assert entry.get("verified_by_human") is not True, key


def prod_client() -> TestClient:
    settings = Settings(environment="prod", llm_provider="none", speech_providers=[])
    return TestClient(create_app(settings), raise_server_exceptions=False)


def test_production_shows_verified_recovery_routes_including_1930():
    body = {"locale": "en", "answers": {"paid_money": True, "payment_method": "upi"}}
    guide = prod_client().post("/v1/recover", json=body).json()
    assert guide["steps"][0]["contact"] == "1930" and guide["steps"][0]["urgent"]
    assert guide["meta"]["unverified_fact_ids"] == []


def test_production_shows_the_verified_group_statistic_card_with_its_caveat():
    answers = {"amount_inr": 40000, "funding_source": "borrowed", "product_class": "derivative"}
    profile = {"monthly_expenses_band": "25k_50k", "liquid_savings_band": "1l_3l",
               "experience": {"derivative": "none"}, "age_band": "lt_30"}  # fmt: skip
    body = {"input": {"type": "text", "content": "Thinking of buying 1 lot of nifty options"},
            "locale": "en", "answers": answers, "profile": profile}  # fmt: skip
    pause = prod_client().post("/v1/analyze", json=body).json()
    assert "group_base_rate" in [c["id"] for c in pause["cards"]]


def test_production_still_hides_the_unverified_tax_card_and_lessons():
    answers = {"amount_inr": 40000, "funding_source": "savings", "product_class": "cash_equity",
               "stage": "consider_action"}  # fmt: skip
    body = {"input": {"type": "text", "content": "Thinking of selling my shares"},
            "locale": "en", "answers": answers}  # fmt: skip
    response = prod_client().post("/v1/analyze", json=body).json()
    assert "capital_gains_holding_period" not in [c["id"] for c in response.get("cards", [])]
    assert response.get("lessons", []) == []  # lesson text itself is not verified yet
