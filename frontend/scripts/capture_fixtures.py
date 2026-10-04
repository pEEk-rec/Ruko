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


def main() -> None:
    """Call /v1/analyze for each case and write the JSON body to the fixtures folder."""
    client = TestClient(create_app())
    for name, body in CASES.items():
        body.setdefault("locale", "en")
        response = client.post("/v1/analyze", json=body)
        data = response.json()
        if isinstance(data.get("meta"), dict):
            data["meta"]["request_id"] = f"fixture-{name}"
            for step in data["meta"].get("trace", []):
                step["duration_ms"] = 0.0
        path = OUT / f"{name}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        outcome = data.get("kind") or data.get("error", {}).get("code")
        print(f"{name}: {response.status_code} {outcome}")


if __name__ == "__main__":
    main()
