"""Regenerate frontend/src/fixtures/*.json from the real backend (in-process, no network).

Runs with the LLM switched off so the output is deterministic (lexicon path only), in the
development environment (unverified facts shown). Run from the repo root:

    .venv/Scripts/python frontend/scripts/capture_fixtures.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

os.environ["RUKO_LLM_PROVIDER"] = "none"
os.environ["RUKO_ENVIRONMENT"] = "dev"
os.environ["RUKO_SPEECH_PROVIDERS"] = ""

from fastapi.testclient import TestClient  # noqa: E402

from ruko.main import create_app  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "src" / "fixtures"
TIP = "Guaranteed 3x return in 7 days. Join our Telegram group, act today!"
BANDS = {"monthly_expenses_band": "25k_50k", "liquid_savings_band": "1l_3l"}

CASES: dict[str, dict] = {
    "clarify_fields": {"input": {"type": "text", "content": TIP}},
    "clarify_stage": {"input": {"type": "text", "content": "good morning"}},
    "pause_l0": {
        "input": {"type": "text", "content": "Thinking of buying some Infosys shares"},
        "answers": {
            "amount_inr": 2000,
            "funding_source": "savings",
            "product_class": "cash_equity",
        },
        "profile": {"experience": {"cash_equity": "some"}},
    },
    "pause_l1": {
        "input": {
            "type": "text",
            "content": "Join now, only today! offer ends soon. Thinking of joining",
        },
        "answers": {
            "amount_inr": 3000,
            "funding_source": "savings",
            "product_class": "cash_equity",
        },
        "profile": {"experience": {"cash_equity": "some"}},
    },
    "pause_l2": {
        "input": {"type": "text", "content": TIP},
        "answers": {
            "amount_inr": 20000,
            "funding_source": "emergency_fund",
            "product_class": "scheme_or_app",
        },
        "profile": BANDS,
    },
    "pause_l3": {
        "input": {"type": "text", "content": "Thinking of buying 1 lot of nifty options"},
        "answers": {
            "amount_inr": 40000,
            "funding_source": "borrowed",
            "product_class": "derivative",
        },
        "profile": {
            **BANDS,
            "rules": {"max_share_of_savings_pct": 10, "no_borrowed_money": True},
            "experience": {"derivative": "none"},
        },
    },
    "pause_l2_hi": {
        "input": {"type": "text", "content": TIP},
        "locale": "hi",
        "answers": {
            "amount_inr": 20000,
            "funding_source": "emergency_fund",
            "product_class": "scheme_or_app",
        },
        "profile": BANDS,
    },
    "pause_scam": {
        "input": {
            "type": "text",
            "content": TIP + " Pay 5000 to rahul9876543210@ybl",
        },
        "profile": BANDS,
    },
    "clarify_hints": {
        "input": {
            "type": "text",
            "content": "Join now, only today! Guaranteed returns, deposit 15000 to start",
        },
        "answers": {"stage": "consider_action"},
    },
    "glossary_unknown": {"input": {"type": "text", "content": "What is a Bollinger band?"}},
    "refusal_prediction": {"input": {"type": "text", "content": "What will Nifty be next year?"}},
    "content_report": {
        "input": {"type": "text", "content": "Is this message real? Guaranteed 3x return in 7 days"}
    },
    "glossary": {"input": {"type": "text", "content": "What is an IPO?"}},
    "recovery": {
        "input": {
            "type": "text",
            "content": "I already paid 5000 by UPI and now they want a fee to withdraw",
        }
    },
    "refusal": {"input": {"type": "text", "content": "Should I buy Reliance?"}},
    "clarify_calc": {
        "input": {"type": "text", "content": "What will my SIP of 5000 a month look like?"}
    },
    "calculation_sip": {
        "input": {"type": "text", "content": "What will my SIP of 5000 a month look like?"},
        "answers": {"calculation": {"months": 120}},
    },
    "calculation_consequence": {
        "input": {
            "type": "text",
            "content": "I put 50k in options with 5x leverage, what if it drops 25%",
        }
    },
    "error_invalid": {"input": {"type": "txt"}},
}


OTHER: dict[str, tuple[str, dict]] = {
    "recover_paid": (
        "/v1/recover",
        {
            "locale": "en",
            "answers": {"paid_money": True, "payment_method": "upi", "cannot_withdraw": True},
        },
    ),
    "journal_review": (
        "/v1/journal/review",
        {
            "locale": "en",
            "as_of": "2026-10-04",
            "entries": [
                {
                    "id": f"e{i}",
                    "date": f"2026-09-{10 + i:02d}",
                    "stage": "consider_action",
                    "product_class": "scheme_or_app",
                    "source_type": "unsolicited_group",
                    "level_shown": "L2",
                    "reason_codes": ["UNSOLICITED_SOURCE"],
                    "action": action,
                    "overrode": action == "went_ahead",
                    "override_reason_given": False,
                    "pause_completed": True,
                    "could_state_why": True,
                    "followed_own_rules": True,
                }
                for i, action in enumerate(["delayed", "went_ahead", "dropped"])
            ],
        },
    ),
    "calculate_sip": (
        "/v1/calculate",
        {
            "locale": "en",
            "inputs": {"tool": "sip", "monthly_inr": 5000, "months": 120, "rates_pct": [9]},
        },
    ),
    "learn_hub": ("/v1/learn", {"locale": "en", "profile": {}}),
    "learn_lesson": (
        "/v1/learn/lesson",
        {"locale": "en", "lesson_id": "mutual_funds_basics", "profile": {}},
    ),
    "calculate_clarify": (
        "/v1/calculate",
        {"locale": "en", "inputs": {"tool": "sip", "monthly_inr": 5000}},
    ),
    "order_intent_l3": (
        "/v1/order-intent",
        {
            "product_class": "derivative",
            "amount_band": {"min_inr": 30000, "max_inr": 50000},
            "borrowed_funds": True,
            "leveraged": True,
            "profile": {
                **BANDS,
                "rules": {"max_share_of_savings_pct": 10, "no_borrowed_money": True},
            },
        },
    ),
    "order_intent_l0": (
        "/v1/order-intent",
        {
            "product_class": "cash_equity",
            "amount_band": {"min_inr": 1000, "max_inr": 2000},
            "profile": {**BANDS, "experience": {"cash_equity": "some"}},
        },
    ),
}


def _scrub(data: dict, name: str) -> None:
    """Make a response deterministic: fixed request ID and zero durations."""
    if isinstance(data.get("meta"), dict):
        data["meta"]["request_id"] = f"fixture-{name}"
        for step in data["meta"].get("trace", []):
            step["duration_ms"] = 0.0


def main() -> None:
    """Call /v1/analyze for each case and write the JSON body to the fixtures folder."""
    client = TestClient(create_app())
    for name, body in CASES.items():
        body.setdefault("locale", "en")
        response = client.post("/v1/analyze", json=body)
        data = response.json()
        _scrub(data, name)
        path = OUT / f"{name}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        outcome = data.get("kind") or data.get("error", {}).get("code")
        print(f"{name}: {response.status_code} {outcome}")
    for name, (route, body) in OTHER.items():
        response = client.post(route, json=body)
        data = response.json()
        _scrub(data, name)
        (OUT / f"{name}.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
        print(f"{name}: {response.status_code} {data.get('kind')}")


if __name__ == "__main__":
    main()
