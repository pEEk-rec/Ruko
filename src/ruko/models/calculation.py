"""Contracts for the ``calculate`` stage: calculator inputs and the calculation response.

Every number in a calculation response comes from the pure functions in ``ruko.tools``.
A calculation is an illustration of arithmetic under stated assumptions, never a
prediction: it always carries ``assumptions`` and at least two scenarios.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from ruko.models.common import CalculatorTool, StrictModel
from ruko.models.responses import Lesson, LessonTopic, ResponseMeta, TemplateRef, TermHit

MAX_AMOUNT_INR = 10_000_000_000
MAX_MONTHS = 600
MAX_YEARS = 50


class CalculationInputs(StrictModel):
    """Calculator inputs the user typed or answered (all optional; bounds are sanity limits).

    Rates and falls are percentages. Missing required inputs become clarify questions;
    missing rates fall back to the labelled example sets in ``data/policy/calculators.yaml``.
    """

    tool: CalculatorTool | None = Field(default=None, description="Which calculator.")
    amount_inr: int | None = Field(
        default=None, ge=1, le=MAX_AMOUNT_INR, description="A one-time amount in rupees."
    )
    monthly_inr: int | None = Field(
        default=None, ge=1, le=MAX_AMOUNT_INR, description="A monthly amount in rupees."
    )
    goal_inr: int | None = Field(
        default=None, ge=1, le=MAX_AMOUNT_INR, description="Goal amount in rupees."
    )
    already_saved_inr: int | None = Field(
        default=None, ge=0, le=MAX_AMOUNT_INR, description="Already saved towards the goal."
    )
    months: int | None = Field(default=None, ge=1, le=MAX_MONTHS, description="Duration.")
    years: int | None = Field(default=None, ge=1, le=MAX_YEARS, description="Duration in years.")
    rates_pct: list[float] = Field(
        default_factory=list, max_length=4, description="Yearly rates the user wants to try."
    )
    drops_pct: list[float] = Field(
        default_factory=list, max_length=4, description="Illustrative falls, in percent."
    )
    leverage: float | None = Field(
        default=None, ge=1, le=50, description="Exposure as a multiple of the money put in."
    )
    trade_value_inr: int | None = Field(
        default=None, ge=1, le=MAX_AMOUNT_INR, description="Value of one trade in rupees."
    )
    trades_per_month: int | None = Field(
        default=None, ge=1, le=1000, description="Trades per month."
    )


class SeriesPoint(StrictModel):
    """One point of a scenario's yearly series (for a chart)."""

    month: int = Field(ge=0, description="Months from the start.")
    invested_inr: int = Field(description="Money put in so far.")
    value_inr: int = Field(description="Value under this scenario's assumption.")


class Scenario(StrictModel):
    """One scenario: an assumption and the arithmetic under it."""

    label: str = Field(description="Rendered label, e.g. 'At an assumed 6% a year'.")
    assumption_pct: float | None = Field(
        default=None, description="The rate, fall or cost assumption behind this scenario."
    )
    values: dict[str, int] = Field(description="Named integer results in rupees.")
    lines: list[str] = Field(default_factory=list, description="Rendered result lines.")
    series: list[SeriesPoint] = Field(default_factory=list, description="Yearly series.")


class CalculationResponse(StrictModel):
    """The calculate path: arithmetic under stated assumptions. Never a prediction."""

    kind: Literal["calculation"] = "calculation"
    tool: CalculatorTool = Field(description="Which calculator ran.")
    inputs: dict[str, int | float | list[float]] = Field(
        description="The numbers used (echoed back; no message text)."
    )
    headline: str = Field(description="Rendered headline.")
    explanation: str = Field(description="Rendered explanation, amounts also in words.")
    assumptions: list[str] = Field(min_length=1, description="Rendered assumptions.")
    scenarios: list[Scenario] = Field(min_length=2, description="Two or more scenarios.")
    is_illustration: Literal[True] = Field(
        default=True, description="Always true: an illustration, not a prediction."
    )
    lessons: list[Lesson] = Field(
        default_factory=list, max_length=2, description="At most 2 lessons for this question."
    )
    learn_next: LessonTopic | None = Field(
        default=None, description="One lesson worth reading next, if none rode along."
    )
    terms: list[TermHit] = Field(
        default_factory=list,
        description="Glossary words used anywhere in this response, tappable in the app.",
    )
    speak: list[TemplateRef] = Field(
        default_factory=list, description="What /v1/speak should read aloud."
    )
    meta: ResponseMeta = Field(description="Metadata.")
