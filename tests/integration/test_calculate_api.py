"""Phase 2 P1: the calculate stage through the HTTP API (fake providers)."""

import json

import pytest

from ruko.guardrails.output_validator import user_facing_texts, validate
from ruko.models.calculation import CalculationResponse
from ruko.providers.llm.fake import FakeLLMProvider
from tests.helpers import analyze_body, make_client

TOOL_QUESTIONS = {
    "sip": "If I invest 10000 a month for 10 years at 12% what do I get?",
    "goal": "How much should I save every month for my goal of 5 lakh in 3 years?",
    "inflation": "What will 1 lakh be worth in 10 years with 6% inflation?",
    "consequence": "What happens to 40000 if this falls 25%?",
    "costs": "brokerage on 20 trades a month of Rs 10,000 each",
}


def post(client, body: dict) -> dict:
    response = client.post("/v1/analyze", json=body)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize(("tool", "text"), TOOL_QUESTIONS.items())
def test_each_tool_returns_an_illustration_with_assumptions_and_scenarios(tool, text):
    data = post(make_client(), analyze_body(text))
    assert data["kind"] == "calculation" and data["tool"] == tool
    assert data["is_illustration"] is True
    assert len(data["scenarios"]) >= 2 and data["assumptions"]
    assert data["meta"]["stage"] == "calculate"
    model = CalculationResponse.model_validate(data)
    for line in user_facing_texts(model):
        assert validate(line, "calculation") == [], line
    assert data["speak"], "calculations can be read aloud"


@pytest.mark.parametrize(
    ("locale", "text"),
    [
        ("en", "What will my SIP of 5000 a month for 10 years look like?"),
        ("hi", "मेरी 5000 की एसआईपी 10 साल में कितनी होगी?"),
        ("kn", "ತಿಂಗಳಿಗೆ 5000 ಎಸ್‌ಐಪಿ 10 ವರ್ಷದಲ್ಲಿ ಎಷ್ಟಾಗುತ್ತದೆ?"),
    ],
)
def test_sip_question_routes_to_the_calculator_in_three_languages(locale, text):
    data = post(make_client(llm=None), analyze_body(text, locale=locale))
    assert data["kind"] == "calculation" and data["tool"] == "sip"
    assert data["meta"]["locale"] == locale and data["meta"]["missing_template_keys"] == []
    assert data["scenarios"][-1]["values"]["value_inr"] == 1_161_695


def test_sip_numbers_and_series_come_from_the_tool():
    data = post(make_client(llm=None), analyze_body(TOOL_QUESTIONS["sip"]))
    twelve = next(s for s in data["scenarios"] if s["assumption_pct"] == 12)
    assert twelve["values"] == {"invested_inr": 1_200_000, "value_inr": 2_323_391,
                                "gain_inr": 1_123_391}  # fmt: skip
    assert [p["month"] for p in twelve["series"]][:3] == [0, 12, 24]
    assert data["inputs"]["rates_pct"] == [0, 6, 12]


def test_missing_input_becomes_a_question_and_the_answer_completes_it():
    client = make_client(llm=None)
    first = post(client, analyze_body("What will my SIP of 5000 a month look like?"))
    assert first["kind"] == "clarify"
    assert [q["field"] for q in first["questions"]] == ["calculation.months"]
    assert first["questions"][0]["options"] == []
    second = post(
        client,
        analyze_body(
            "What will my SIP of 5000 a month look like?", answers={"calculation": {"months": 60}}
        ),
    )
    assert second["kind"] == "calculation" and second["inputs"]["months"] == 60


def test_unclear_tool_asks_which_calculation_and_tax_is_not_offered():
    data = post(make_client(llm=None), analyze_body("calculate something for me"))
    (question,) = data["questions"]
    assert question["field"] == "calculation.tool"
    values = [o["value"] for o in question["options"]]
    assert values == ["sip", "goal", "inflation", "consequence", "costs"]


def test_answered_tool_and_numbers_run_without_any_words():
    answers = {"stage": "calculate",
               "calculation": {"tool": "inflation", "amount_inr": 50000, "years": 5}}  # fmt: skip
    data = post(make_client(llm=None), analyze_body("numbers please", answers=answers))
    assert data["kind"] == "calculation" and data["tool"] == "inflation"


def test_llm_may_choose_the_tool_but_never_the_numbers():
    reply = json.dumps(
        {"is_financial_decision": False, "stage": "calculate", "calculator_tool": "consequence",
         "amount_inr": 999999, "signals": [], "request_classes": []}
    )  # fmt: skip
    llm = FakeLLMProvider([reply])
    data = post(make_client(llm=llm), analyze_body("hmm 40000, say it goes 25% lower?"))
    assert data["kind"] == "calculation" and data["tool"] == "consequence"
    assert data["inputs"]["amount_inr"] == 40_000  # from the user's words, not the LLM
    assert data["meta"]["stage_source"] == "llm"


def test_leverage_shows_a_loss_bigger_than_the_money_put_in():
    text = "I put 50k in options with 5x leverage, what if it drops 25%"
    data = post(make_client(llm=None), analyze_body(text))
    drop = next(s for s in data["scenarios"] if s["assumption_pct"] == 25)
    assert drop["values"]["left_inr"] == -12_500
    assert any("more than the money put in" in line for line in drop["lines"])


def test_calculation_text_never_predicts():
    assert "calculation_assertion" in validate(
        "You will get ₹11,61,695 after 10 years.", "calculation"
    )
    assert "calculation_assertion" in validate("The expected return is 12%.", "calculation")
    assert "calculation_assertion" in validate("आपको ₹5,000 मिलेगा।", "calculation")
    assert "calculation_assertion" in validate("ನಿಮಗೆ ₹5,000 ಸಿಗುತ್ತದೆ.", "calculation")
    assert (
        validate("At an assumed 12% a year the arithmetic gives ₹11,61,695.", "calculation") == []
    )


def test_prediction_and_best_fund_requests_are_still_refused():
    client = make_client(llm=None)
    assert post(client, analyze_body("What will Nifty be next year?"))["refusal_class"] == (
        "PREDICTION_REQUEST"
    )
    assert post(client, analyze_body("Which fund gives the best return?"))["refusal_class"] == (
        "ADVICE_REQUEST"
    )


def test_stage_question_offers_the_calculator():
    data = post(make_client(llm=None), analyze_body("good morning"))
    assert "calculate" in [o["value"] for o in data["questions"][0]["options"]]


def test_calculation_can_be_read_aloud():
    client = make_client(llm=None)
    data = post(client, analyze_body(TOOL_QUESTIONS["consequence"]))
    speech = client.post("/v1/speak", json={"locale": "en", "items": data["speak"][:6]})
    assert speech.status_code == 200, speech.text
    assert speech.json()["kind"] == "speech"


def test_openapi_lists_the_calculation_kind():
    schema = make_client().get("/openapi.json").json()
    assert "CalculationResponse" in schema["components"]["schemas"]
