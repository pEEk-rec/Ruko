"""Read calculator inputs from the user's own words, deterministically.

Tool choice and unit words live in the ``calculator`` section of ``data/stages/*.yaml``
(every locale runs on every input, like the stage patterns). The parser only reads
numbers the user typed: amounts (with ₹ / lakh / crore / thousand), monthly amounts,
durations in months or years, percentages, leverage and trades per month. It never guesses
a missing number; missing inputs become clarify questions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache

from ruko.data_files import data_dir, load_yaml
from ruko.guardrails.normalize import normalize, strip_zero_width
from ruko.models.calculation import MAX_AMOUNT_INR, MAX_MONTHS, MAX_YEARS, CalculationInputs
from ruko.models.common import CalculatorTool

_FLAGS = re.IGNORECASE | re.UNICODE
_NUMBER = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{2,3})+|\d+)(?:\.(\d+))?(?!\d|,\d)")
"""A number with optional Indian or Western grouping ("2,50,000", "250,000"). A comma counts
as grouping only when a digit follows it; "40000, say" ends the number at the comma."""
_LEADING_NUMBER = re.compile(r"\s*\d")
_MULTIPLIERS = {"thousand": 1_000, "lakh": 100_000, "crore": 10_000_000}
_LOOKAHEAD = 30
_LOOKBEHIND = 24
MIN_BARE_AMOUNT = 100
"""A bare number below this (no ₹, unit or 'per month') is not read as rupees."""


@dataclass(frozen=True)
class CalculatorPatterns:
    """Compiled tool and unit patterns from every locale."""

    tools: tuple[tuple[CalculatorTool, tuple[re.Pattern[str], ...]], ...]
    units: dict[str, re.Pattern[str]]
    """Each unit category as one pattern anchored at the start of the text after a number."""
    per_month_before: re.Pattern[str]
    currency_before: re.Pattern[str]
    percent_before: re.Pattern[str]
    leverage: tuple[re.Pattern[str], ...]
    trades_per_month: tuple[re.Pattern[str], ...]


def _alternation(words: list[str]) -> str:
    """Longest first, so 'lakhs' wins over 'l'. Latin words must end at a word boundary."""
    parts = []
    for word in sorted(set(words), key=len, reverse=True):
        escaped = re.escape(strip_zero_width(word.lower()))
        parts.append(
            escaped + r"(?![a-z])" if word[-1:].isascii() and word[-1].isalpha() else escaped
        )
    return "|".join(parts)


@lru_cache(maxsize=1)
def get_calculator_patterns() -> CalculatorPatterns:
    """Load and merge the ``calculator`` sections of ``data/stages/*.yaml`` (cached)."""
    tools: dict[CalculatorTool, list[re.Pattern[str]]] = {}
    units: dict[str, list[str]] = {}
    leverage: list[re.Pattern[str]] = []
    trades: list[re.Pattern[str]] = []
    for path in sorted((data_dir() / "stages").glob("*.yaml")):
        section = load_yaml("stages", path.name).get("calculator") or {}
        for name, patterns in (section.get("tools") or {}).items():
            compiled = [re.compile(strip_zero_width(p), _FLAGS) for p in patterns]
            tools.setdefault(CalculatorTool(name), []).extend(compiled)
        for name, words in (section.get("units") or {}).items():
            units.setdefault(name, []).extend(words)
        leverage += [re.compile(p, _FLAGS) for p in section.get("leverage") or []]
        trades += [re.compile(p, _FLAGS) for p in section.get("trades_per_month") or []]
    order = [CalculatorTool.CONSEQUENCE, CalculatorTool.COSTS, CalculatorTool.SIP,
             CalculatorTool.GOAL, CalculatorTool.INFLATION]  # fmt: skip
    return CalculatorPatterns(
        tools=tuple((t, tuple(tools.get(t, []))) for t in order),
        units={
            name: re.compile(r"\s*(?:" + _alternation(words) + ")", _FLAGS)
            for name, words in units.items()
        },  # fmt: skip
        per_month_before=re.compile(
            r"(?:"
            + _alternation(units.get("per_month", []))
            + r")\s*(?:"
            + _alternation(units.get("currency", []))
            + r")?\s*$",
            _FLAGS,
        ),
        currency_before=re.compile(
            r"(?:" + _alternation(units.get("currency", [])) + r")\s*$", _FLAGS
        ),
        percent_before=re.compile(
            r"(?:" + _alternation([w for w in units.get("percent", []) if w != "%"]) + r")\s*$",
            _FLAGS,
        ),
        leverage=tuple(leverage),
        trades_per_month=tuple(trades),
    )


def choose_tool(text: str) -> CalculatorTool | None:
    """Return the first tool whose patterns match, or None if no tool is clear."""
    normalized = normalize(text)
    for tool, patterns in get_calculator_patterns().tools:
        if any(p.search(normalized) for p in patterns):
            return tool
    return None


@dataclass
class Numbers:
    """Numbers found in the text, by kind, in the order they appear."""

    amounts: list[int] = field(default_factory=list)
    monthly: list[int] = field(default_factory=list)
    percents: list[float] = field(default_factory=list)
    months: list[int] = field(default_factory=list)
    years: list[int] = field(default_factory=list)


def _starts(units: dict[str, re.Pattern[str]], name: str, rest: str) -> re.Match[str] | None:
    pattern = units.get(name)
    return pattern.match(rest) if pattern else None


def read_numbers(text: str) -> Numbers:
    """Classify every number in the text by the unit words around it."""
    pats = get_calculator_patterns()
    units = pats.units
    normalized = normalize(text)
    found = Numbers()
    for match in _NUMBER.finditer(normalized):
        whole = match.group(1).replace(",", "")
        value = float(f"{whole}.{match.group(2)}") if match.group(2) else float(whole)
        rest = normalized[match.end() : match.end() + _LOOKAHEAD]
        before = normalized[max(0, match.start() - _LOOKBEHIND) : match.start()]
        percent_after = _starts(units, "percent", rest)
        # "ಶೇಕಡಾ 25" puts the percent word first: a percent word followed by another
        # number belongs to that number, not to this one.
        if percent_after and _LEADING_NUMBER.match(rest[percent_after.end() :]):
            percent_after = None
        if percent_after or pats.percent_before.search(before):
            found.percents.append(value)
            continue
        multiplier = 1
        for name, factor in _MULTIPLIERS.items():
            unit = _starts(units, name, rest)
            if unit:
                multiplier, rest = factor, rest[unit.end() :]
                break
        if multiplier == 1 and _starts(units, "years", rest) and value == int(value):
            found.years.append(int(value))
            continue
        is_duration = multiplier == 1 and value == int(value)
        if is_duration and _starts(units, "months", rest) and not _starts(units, "per_month", rest):
            found.months.append(int(value))
            continue
        amount = round(value * multiplier)
        has_currency = bool(pats.currency_before.search(before))
        monthly = bool(_starts(units, "per_month", rest) or pats.per_month_before.search(before))
        if multiplier == 1 and not (has_currency or monthly) and amount < MIN_BARE_AMOUNT:
            continue
        if 1 <= amount <= MAX_AMOUNT_INR:
            (found.monthly if monthly else found.amounts).append(amount)
    return found


def _first_number(patterns: tuple[re.Pattern[str], ...], text: str) -> float | None:
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return float(match.group(1))
    return None


def _months(numbers: Numbers) -> int | None:
    if numbers.months and 1 <= numbers.months[0] <= MAX_MONTHS:
        return numbers.months[0]
    if numbers.years and 1 <= numbers.years[0] <= MAX_MONTHS // 12:
        return numbers.years[0] * 12
    return None


def _years(numbers: Numbers) -> int | None:
    if numbers.years and 1 <= numbers.years[0] <= MAX_YEARS:
        return numbers.years[0]
    if numbers.months and numbers.months[0] % 12 == 0 and numbers.months[0] // 12 <= MAX_YEARS:
        return numbers.months[0] // 12
    return None


def read_inputs(text: str, tool: CalculatorTool | None) -> CalculationInputs:
    """Read calculator inputs for a tool from the user's text (only what is clearly there).

    Args:
        text: The user's message (patterns run in memory only).
        tool: The chosen tool, or None (then only the tool-independent fields are read).

    Returns:
        The inputs found; anything not clearly stated is left empty.
    """
    pats = get_calculator_patterns()
    normalized = normalize(text)
    numbers = read_numbers(text)
    lump = numbers.amounts[0] if numbers.amounts else None
    fields: dict[str, object] = {"tool": tool, "rates_pct": numbers.percents[:4]}
    if tool == CalculatorTool.SIP:
        monthly = numbers.monthly[0] if numbers.monthly else lump
        fields |= {"monthly_inr": monthly, "months": _months(numbers)}
    elif tool == CalculatorTool.GOAL:
        goal = max(numbers.amounts) if numbers.amounts else None
        fields |= {"goal_inr": goal, "months": _months(numbers)}
    elif tool == CalculatorTool.INFLATION:
        fields |= {"amount_inr": lump, "years": _years(numbers)}
    elif tool == CalculatorTool.CONSEQUENCE:
        leverage = _first_number(pats.leverage, normalized)
        fields |= {
            "amount_inr": lump or (numbers.monthly[0] if numbers.monthly else None),
            "drops_pct": numbers.percents[:4],
            "rates_pct": [],
            "leverage": leverage if leverage and 1 <= leverage <= 50 else None,
        }
    elif tool == CalculatorTool.COSTS:
        trades = _first_number(pats.trades_per_month, normalized)
        fields |= {
            "trade_value_inr": lump,
            "trades_per_month": int(trades) if trades and 1 <= trades <= 1000 else None,
            "months": _months(numbers),
            "rates_pct": [],
        }
    return CalculationInputs.model_validate(fields)
