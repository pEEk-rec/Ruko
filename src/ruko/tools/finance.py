"""Pure calculator arithmetic. Integer rupees in and out, no I/O, no randomness.

These are illustrations of arithmetic under assumptions, never predictions. Each function
takes several rates (or falls) and returns one result per assumption, so a caller always
has scenarios to show side by side.

Conventions (stated to the user as assumptions):
- A yearly rate ``r`` percent compounds monthly at ``r / 12`` percent per month.
- Monthly contributions are made at the start of each month (an "annuity due").
- Results are rounded to whole rupees at the end, never in between.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ruko.engine.exposure import adverse_moves


def _monthly_rate(annual_pct: float) -> float:
    return annual_pct / 100 / 12


def _annuity_due_factor(monthly_rate: float, months: int) -> float:
    """Value after ``months`` of contributing 1 at the start of every month."""
    if monthly_rate == 0:
        return float(months)
    # expm1/log1p keep (1 + i)^n - 1 accurate when i is tiny (plain powers round it to 0).
    growth_minus_one = math.expm1(months * math.log1p(monthly_rate))
    return growth_minus_one / monthly_rate * (1 + monthly_rate)


def _check_months(months: int) -> None:
    if months < 0:
        raise ValueError("months must be zero or more")


# --- SIP --------------------------------------------------------------------------------


@dataclass(frozen=True)
class SipPoint:
    """Money put in and its value after ``month`` months."""

    month: int
    invested_inr: int
    value_inr: int


@dataclass(frozen=True)
class SipResult:
    """One SIP scenario."""

    annual_rate_pct: float
    invested_inr: int
    value_inr: int
    series: tuple[SipPoint, ...]

    @property
    def gain_inr(self) -> int:
        """Value minus money put in (can be zero)."""
        return self.value_inr - self.invested_inr


def sip_value(monthly_inr: int, months: int, annual_rate_pct: float) -> int:
    """Value of a monthly SIP after ``months`` at an assumed yearly rate.

    Formula: ``FV = P * ((1 + i)^n - 1) / i * (1 + i)`` with ``i = rate / 12``;
    at a 0% rate, ``FV = P * n``.
    """
    _check_months(months)
    return round(monthly_inr * _annuity_due_factor(_monthly_rate(annual_rate_pct), months))


def _yearly_months(months: int) -> list[int]:
    points = list(range(0, months + 1, 12))
    if points[-1] != months:
        points.append(months)
    return points


def sip_illustration(
    monthly_inr: int, months: int, annual_rates_pct: list[float]
) -> list[SipResult]:
    """SIP value per assumed rate, with a yearly series for charting.

    Args:
        monthly_inr: Amount put in at the start of every month.
        months: Number of months.
        annual_rates_pct: Assumed yearly rates (one scenario each).

    Returns:
        One result per rate, in the order given.
    """
    _check_months(months)
    results = []
    for rate in annual_rates_pct:
        series = tuple(
            SipPoint(m, monthly_inr * m, sip_value(monthly_inr, m, rate))
            for m in _yearly_months(months)
        )
        results.append(
            SipResult(rate, monthly_inr * months, sip_value(monthly_inr, months, rate), series)
        )
    return results


# --- Goal -------------------------------------------------------------------------------


@dataclass(frozen=True)
class GoalResult:
    """Monthly amount that reaches a goal under one assumed rate."""

    annual_rate_pct: float
    monthly_needed_inr: int
    invested_inr: int


def goal_contribution(
    goal_inr: int, months: int, annual_rates_pct: list[float], already_saved_inr: int = 0
) -> list[GoalResult]:
    """Monthly contribution needed to reach a goal, per assumed rate.

    The amount already saved is assumed to grow at the same rate. The monthly amount is
    rounded *up* so that the arithmetic reaches the goal; it is zero if the saved amount
    already gets there.

    Formula: ``P = (goal - saved * (1 + i)^n) / annuity_due_factor(i, n)``.
    """
    if months < 1:
        raise ValueError("months must be at least 1")
    results = []
    for rate in annual_rates_pct:
        i = _monthly_rate(rate)
        saved_later = already_saved_inr * (1 + i) ** months
        shortfall = max(0.0, goal_inr - saved_later)
        monthly = math.ceil(shortfall / _annuity_due_factor(i, months) - 1e-9)
        monthly = max(0, monthly)
        results.append(GoalResult(rate, monthly, monthly * months + already_saved_inr))
    return results


# --- Inflation --------------------------------------------------------------------------


@dataclass(frozen=True)
class InflationResult:
    """What an amount means after some years at one assumed inflation rate."""

    inflation_pct: float
    future_cost_inr: int
    """What costs ``amount`` today would cost this much later."""
    today_value_inr: int
    """What ``amount`` received later would buy in today's rupees."""


def inflation_purchasing_power(
    amount_inr: int, years: int, inflation_rates_pct: list[float]
) -> list[InflationResult]:
    """Future cost and today's-value of an amount, per assumed yearly inflation rate.

    Formulas: ``future = amount * (1 + r)^years``; ``today = amount / (1 + r)^years``.
    """
    if years < 0:
        raise ValueError("years must be zero or more")
    results = []
    for rate in inflation_rates_pct:
        factor = (1 + rate / 100) ** years
        results.append(
            InflationResult(rate, round(amount_inr * factor), round(amount_inr / factor))
        )
    return results


# --- Consequence of a fall --------------------------------------------------------------


@dataclass(frozen=True)
class ConsequenceResult:
    """Rupee outcome of one illustrative fall. Never a probability."""

    drop_pct: float
    exposure_inr: int
    loss_inr: int
    left_inr: int
    """Money put in minus the loss; negative means the loss is bigger than the money put in."""

    @property
    def exceeds_amount(self) -> bool:
        """True if the loss is larger than the money put in (possible with leverage)."""
        return self.left_inr < 0


def consequence(
    amount_inr: int, drops_pct: list[float], leverage: float = 1.0
) -> list[ConsequenceResult]:
    """What each illustrative fall would mean in rupees.

    With leverage ``L`` the position is ``amount * L``, so a fall of ``d``% loses
    ``amount * L * d / 100``, which can exceed the money put in. Reuses the engine's
    ``adverse_moves`` so the pause screen and the calculator agree.
    """
    if leverage < 1:
        raise ValueError("leverage must be at least 1")
    exposure = round(amount_inr * leverage)
    moves = adverse_moves(exposure, tuple(drops_pct))
    return [
        ConsequenceResult(m.move_pct, exposure, m.loss_inr, amount_inr - m.loss_inr) for m in moves
    ]


# --- Trading costs ----------------------------------------------------------------------


@dataclass(frozen=True)
class CostAssumption:
    """One cost assumption: a fixed amount per trade plus a percentage of trade value."""

    per_trade_inr: float
    pct_of_value: float


@dataclass(frozen=True)
class CostResult:
    """Costs over a period under one assumption."""

    assumption: CostAssumption
    trades: int
    per_trade_cost_inr: int
    total_cost_inr: int


def cost_illustration(
    trade_value_inr: int, trades_per_month: int, months: int, assumptions: list[CostAssumption]
) -> list[CostResult]:
    """Total trading costs over a period, per cost assumption.

    Formula: ``per trade = fixed + value * pct / 100``; ``total = per trade * trades``.
    The cost parameters are assumptions the user supplies or labelled examples, never a
    claim about any broker's actual charges.
    """
    _check_months(months)
    trades = trades_per_month * months
    results = []
    for a in assumptions:
        per_trade = a.per_trade_inr + trade_value_inr * a.pct_of_value / 100
        results.append(CostResult(a, trades, round(per_trade), round(per_trade * trades)))
    return results
