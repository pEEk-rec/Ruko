"""Pure arithmetic on the user's own numbers. No I/O, no LLM, no predictions.

Profiles usually carry bands, so every result is a range plus a ``typical`` value.
When the device sends an exact figure, low == high == typical.
"""

from __future__ import annotations

from dataclasses import dataclass

from ruko.engine.policy import Band, InterventionPolicy
from ruko.models.decision import AdverseMove, ComputedNumbers, MoneyRange, NumberRange
from ruko.models.event import DecisionEvent
from ruko.models.profile import UserProfile


@dataclass(frozen=True)
class Quantity:
    """A rupee quantity known exactly or as a band."""

    low: int
    high: int | None
    typical: int
    exact: bool

    @property
    def low_for_division(self) -> int:
        """Lower edge, or typical when the edge is 0 (avoids dividing by zero)."""
        return self.low if self.low > 0 else self.typical

    @property
    def high_or_typical(self) -> int:
        """Upper edge, or typical when the band is open-ended."""
        return self.high if self.high is not None else self.typical


def _from(exact: int | None, band_name: str | None, bands: dict[str, Band]) -> Quantity | None:
    if exact is not None:
        return Quantity(exact, exact, exact, True)
    if band_name is None:
        return None
    band = bands[band_name]
    return Quantity(band.low, band.high, band.typical, False)


def monthly_expenses(profile: UserProfile, policy: InterventionPolicy) -> Quantity | None:
    """Return the user's monthly expenses (exact or band), if known."""
    return _from(profile.monthly_expenses_inr, profile.monthly_expenses_band, policy.expense_bands)


def liquid_savings(profile: UserProfile, policy: InterventionPolicy) -> Quantity | None:
    """Return the user's liquid savings (exact or band), if known."""
    return _from(profile.liquid_savings_inr, profile.liquid_savings_band, policy.savings_bands)


def months_of_expenses(amount: int, expenses: Quantity) -> NumberRange:
    """Express an amount as months of the user's expenses."""
    return NumberRange(
        low=round(amount / expenses.high_or_typical, 1),
        high=round(amount / expenses.low_for_division, 1),
        typical=round(amount / expenses.typical, 1),
    )


def share_of_savings_pct(amount: int, savings: Quantity) -> NumberRange | None:
    """Express an amount as a % of liquid savings; None when savings are exactly zero."""
    if savings.typical <= 0:
        return None
    return NumberRange(
        low=round(100 * amount / savings.high_or_typical, 1),
        high=round(100 * amount / savings.low_for_division, 1),
        typical=round(100 * amount / savings.typical, 1),
    )


def remaining_savings(amount: int, savings: Quantity) -> MoneyRange:
    """Liquid savings left after this decision (negative means a shortfall)."""
    return MoneyRange(
        low=savings.low - amount,
        high=savings.high_or_typical - amount,
        typical=savings.typical - amount,
    )


def remaining_buffer_months(remaining: MoneyRange, expenses: Quantity) -> NumberRange:
    """Savings left after this decision, in months of expenses."""
    return NumberRange(
        low=round(max(remaining.low, 0) / expenses.high_or_typical, 1),
        high=round(max(remaining.high, 0) / expenses.low_for_division, 1),
        typical=round(max(remaining.typical, 0) / expenses.typical, 1),
    )


def adverse_moves(amount: int, percentages: tuple[float, ...]) -> list[AdverseMove]:
    """Illustrate what an X% fall in the value put in means in rupees. Not a prediction."""
    return [
        AdverseMove(move_pct=pct, loss_inr=round(amount * pct / 100), exposure_inr=amount)
        for pct in percentages
    ]


def compute_numbers(
    event: DecisionEvent, profile: UserProfile, policy: InterventionPolicy
) -> ComputedNumbers:
    """Compute every personal number the pause screen may show.

    Args:
        event: The decision.
        profile: The device snapshot.
        policy: Intervention policy (bands, illustration percentages).

    Returns:
        ``ComputedNumbers``; fields stay None when inputs are missing.
    """
    amount = event.amount_inr
    if amount is None:
        return ComputedNumbers()
    expenses = monthly_expenses(profile, policy)
    savings = liquid_savings(profile, policy)
    exact = all(q.exact for q in (expenses, savings) if q is not None)
    numbers = ComputedNumbers(
        amount_inr=amount,
        basis="none" if expenses is None and savings is None else ("exact" if exact else "band"),
    )
    if expenses is not None:
        numbers.months_of_expenses = months_of_expenses(amount, expenses)
    if savings is not None:
        numbers.share_of_savings_pct = share_of_savings_pct(amount, savings)
        numbers.remaining_savings_inr = remaining_savings(amount, savings)
        if expenses is not None:
            numbers.remaining_buffer_months = remaining_buffer_months(
                numbers.remaining_savings_inr, expenses
            )
    if event.product_class in policy.leveraged_product_classes:
        numbers.adverse_moves = adverse_moves(amount, policy.adverse_move_illustrations_pct)
    return numbers
