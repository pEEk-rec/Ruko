"""Assemble the ``calculate`` path: merge inputs, ask for what is missing, render results.

Inputs come from three places, in this order of trust: what the user answered in the app
(``answers.calculation``), what the deterministic parser read from their words, and what
the LLM proposed (used only to fill gaps). Every number shown comes from
``ruko.tools.finance``; every sentence comes from a ``calculation`` template.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from functools import lru_cache

from ruko.data_files import load_yaml
from ruko.language.numbers import amount_in_words, rupees
from ruko.language.templates import Renderer
from ruko.models.calculation import CalculationInputs, Scenario, SeriesPoint
from ruko.models.common import CalculationField, CalculatorTool
from ruko.models.responses import ClarifyOption, ClarifyQuestion, TemplateRef
from ruko.tools import finance

REQUIRED: dict[CalculatorTool, tuple[str, ...]] = {
    CalculatorTool.SIP: ("monthly_inr", "months"),
    CalculatorTool.GOAL: ("goal_inr", "months"),
    CalculatorTool.INFLATION: ("amount_inr", "years"),
    CalculatorTool.CONSEQUENCE: ("amount_inr",),
    CalculatorTool.COSTS: ("trade_value_inr", "trades_per_month"),
}
"""Inputs each tool cannot run without (missing ones become clarify questions)."""

TOOL_ORDER = (
    CalculatorTool.SIP,
    CalculatorTool.GOAL,
    CalculatorTool.INFLATION,
    CalculatorTool.CONSEQUENCE,
    CalculatorTool.COSTS,
)

TEMPLATE_KEYS = frozenset(
    {
        "stage.option.calculate",
        "calc.question.tool",
        *(f"calc.tool.{tool.value}" for tool in TOOL_ORDER),
        *(f"calc.question.{name}" for names in REQUIRED.values() for name in names),
        "calc.assumption.illustration",
        "calc.assumption.example_rates",
        "calc.assumption.monthly_compounding",
        "calc.assumption.returns_vary",
        "calc.assumption.example_inflation",
        "calc.assumption.example_drops",
        "calc.label.rate",
        "calc.label.inflation",
        "calc.label.drop",
        "calc.label.cost_fixed",
        "calc.label.cost_pct",
        "calc.label.cost_both",
        "calc.sip.headline",
        "calc.sip.line.invested",
        "calc.sip.line.value",
        "calc.sip.explanation",
        "calc.goal.headline",
        "calc.goal.line.monthly",
        "calc.goal.line.invested",
        "calc.goal.explanation",
        "calc.goal.assumption.saved",
        "calc.goal.assumption.none_saved",
        "calc.inflation.headline",
        "calc.inflation.line.future_cost",
        "calc.inflation.line.today_value",
        "calc.inflation.explanation",
        "calc.consequence.headline",
        "calc.consequence.line.loss",
        "calc.consequence.line.left",
        "calc.consequence.line.exceeds",
        "calc.consequence.explanation",
        "calc.consequence.assumption.no_leverage",
        "calc.consequence.assumption.leverage",
        "calc.costs.headline",
        "calc.costs.line.per_trade",
        "calc.costs.line.total",
        "calc.costs.explanation",
        "calc.costs.assumption.hypothetical",
        "calc.costs.assumption.months",
    }
)
"""Template keys the calculate path can render (checked by the template linter)."""


# --- Policy -----------------------------------------------------------------------------


@dataclass(frozen=True)
class CalculatorPolicy:
    """``data/policy/calculators.yaml``."""

    version: str
    enabled: frozenset[CalculatorTool]
    example_rates: dict[CalculatorTool, tuple[float, ...]]
    example_drops: tuple[float, ...]
    cost_assumptions: tuple[finance.CostAssumption, ...]
    cost_default_months: int
    bounds: dict[str, tuple[float, float]]
    max_scenarios: int
    min_scenarios: int


@lru_cache(maxsize=1)
def get_calculator_policy() -> CalculatorPolicy:
    """Load the calculator policy (cached)."""
    raw = load_yaml("policy", "calculators.yaml")
    tools = raw["tools"]
    return CalculatorPolicy(
        version=str(raw["version"]),
        enabled=frozenset(CalculatorTool(k) for k, v in tools.items() if v.get("enabled")),
        example_rates={
            CalculatorTool(k): tuple(float(x) for x in v["example_rates_pct"])
            for k, v in tools.items()
            if "example_rates_pct" in v
        },
        example_drops=tuple(float(x) for x in tools["consequence"]["example_drops_pct"]),
        cost_assumptions=tuple(
            finance.CostAssumption(float(a["per_trade_inr"]), float(a["pct_of_value"]))
            for a in tools["costs"]["example_assumptions"]
        ),
        cost_default_months=int(tools["costs"]["default_months"]),
        bounds={k: (float(v[0]), float(v[1])) for k, v in raw["bounds"].items()},
        max_scenarios=int(raw["max_scenarios"]),
        min_scenarios=int(raw["min_scenarios"]),
    )


# --- Inputs -----------------------------------------------------------------------------


def merge_inputs(
    answered: CalculationInputs | None,
    from_text: CalculationInputs,
    from_llm: CalculationInputs | None = None,
) -> CalculationInputs:
    """Combine inputs: the user's answers win, then their words, then the LLM (gaps only)."""
    merged: dict[str, object] = {}
    sources = [s for s in (answered, from_text, from_llm) if s is not None]
    for name in CalculationInputs.model_fields:
        for source in sources:
            value = getattr(source, name)
            if value not in (None, []):
                merged[name] = value
                break
    return CalculationInputs.model_validate(merged)


def missing_fields(
    inputs: CalculationInputs, policy: CalculatorPolicy | None = None
) -> list[CalculationField]:
    """Return the calculator fields to ask for (the tool first, if it is not clear)."""
    policy = policy or get_calculator_policy()
    if inputs.tool is None or inputs.tool not in policy.enabled:
        return ["calculation.tool"]
    return [
        f"calculation.{name}"  # type: ignore[misc]
        for name in REQUIRED[inputs.tool]
        if getattr(inputs, name) is None
    ]


def clarify_questions(
    fields: list[CalculationField], renderer: Renderer, policy: CalculatorPolicy | None = None
) -> tuple[list[ClarifyQuestion], list[TemplateRef]]:
    """Render clarify questions for missing calculator fields."""
    policy = policy or get_calculator_policy()
    questions: list[ClarifyQuestion] = []
    refs: list[TemplateRef] = []
    for name in fields:
        short = name.removeprefix("calculation.")
        key = f"calc.question.{short}"
        options: list[ClarifyOption] = []
        if short == "tool":
            options = [
                ClarifyOption(value=t.value, label=renderer.text(f"calc.tool.{t.value}"))
                for t in TOOL_ORDER
                if t in policy.enabled
            ]
        questions.append(ClarifyQuestion(field=name, text=renderer.text(key), options=options))
        refs.append(TemplateRef(key=key))
    return questions, refs


def scenario_values(
    user: list[float],
    examples: tuple[float, ...],
    bounds: tuple[float, float],
    policy: CalculatorPolicy,
) -> tuple[list[float], bool]:
    """Pick the assumptions to show: the user's (within bounds) plus labelled examples.

    Always returns at least ``min_scenarios`` values (examples fill in) and at most
    ``max_scenarios``, sorted. The flag says whether any example value was used.
    """
    low, high = bounds
    chosen: list[float] = []
    for value in user:
        if low <= value <= high and value not in chosen:
            chosen.append(value)
    chosen = chosen[: policy.max_scenarios]
    used_example = False
    target = max(policy.min_scenarios, min(policy.max_scenarios, len(chosen) + len(examples)))
    for value in examples:
        if len(chosen) >= target:
            break
        if value not in chosen:
            chosen.append(value)
            used_example = True
    return sorted(chosen), used_example


# --- Rendering --------------------------------------------------------------------------


def pct(value: float) -> str:
    """Format a percentage without trailing zeros: 6.0 -> '6', 0.5 -> '0.5'."""
    return f"{value:.2f}".rstrip("0").rstrip(".")


@dataclass
class _Lines:
    """Rendered lines plus the matching speech references."""

    renderer: Renderer
    texts: list[str] = field(default_factory=list)
    refs: list[TemplateRef] = field(default_factory=list)

    def add(self, key: str, **slots: str) -> str:
        text = self.renderer.text(key, **slots)
        self.texts.append(text)
        self.refs.append(TemplateRef(key=key, slots=slots))
        return text


@dataclass
class CalculationContent:
    """Everything in a calculation response except the metadata."""

    tool: CalculatorTool
    inputs: dict[str, int | float | list[float]]
    headline: str
    explanation: str
    assumptions: list[str]
    scenarios: list[Scenario]
    speak: list[TemplateRef]


def _words(n: int, renderer: Renderer) -> str:
    return amount_in_words(abs(n), renderer.locale)


def _scenario(
    renderer: Renderer,
    label_key: str,
    label_slots: dict[str, str],
    value: float | None,
    values: dict[str, int],
    line_specs: list[tuple[str, dict[str, str]]],
    series: list[SeriesPoint] | None = None,
) -> tuple[Scenario, list[TemplateRef]]:
    lines = _Lines(renderer)
    for key, slots in line_specs:
        lines.add(key, **slots)
    label = renderer.text(label_key, **label_slots)
    refs = [TemplateRef(key=label_key, slots=label_slots), *lines.refs]
    scenario = Scenario(
        label=label, assumption_pct=value, values=values, lines=lines.texts, series=series or []
    )
    return scenario, refs


def _sip(inputs: CalculationInputs, r: Renderer, policy: CalculatorPolicy) -> CalculationContent:
    assert inputs.monthly_inr is not None and inputs.months is not None
    rates, example = scenario_values(
        inputs.rates_pct,
        policy.example_rates[CalculatorTool.SIP],
        policy.bounds["rate_pct"],
        policy,
    )
    results = finance.sip_illustration(inputs.monthly_inr, inputs.months, rates)
    head = _Lines(r)
    head.add("calc.sip.headline", monthly=rupees(inputs.monthly_inr), months=str(inputs.months))
    scenarios, refs = [], list(head.refs)
    for res in results:
        scenario, s_refs = _scenario(
            r,
            "calc.label.rate",
            {"rate": pct(res.annual_rate_pct)},
            res.annual_rate_pct,
            {
                "invested_inr": res.invested_inr,
                "value_inr": res.value_inr,
                "gain_inr": res.gain_inr,
            },
            [
                ("calc.sip.line.invested", {"invested": rupees(res.invested_inr)}),
                ("calc.sip.line.value", {"value": rupees(res.value_inr)}),
            ],
            [
                SeriesPoint(month=p.month, invested_inr=p.invested_inr, value_inr=p.value_inr)
                for p in res.series
            ],
        )
        scenarios.append(scenario)
        refs += s_refs
    low, high = results[0], results[-1]
    explanation = r.text(
        "calc.sip.explanation",
        invested=rupees(low.invested_inr),
        invested_words=_words(low.invested_inr, r),
        low_rate=pct(low.annual_rate_pct),
        low_value=rupees(low.value_inr),
        high_rate=pct(high.annual_rate_pct),
        high_value=rupees(high.value_inr),
        high_words=_words(high.value_inr, r),
    )
    keys = ["calc.assumption.illustration"]
    keys += ["calc.assumption.example_rates"] if example else []
    keys += ["calc.assumption.monthly_compounding", "calc.assumption.returns_vary"]
    return _content(
        CalculatorTool.SIP, inputs, rates, head, explanation, keys, [], scenarios, refs, r
    )


def _goal(inputs: CalculationInputs, r: Renderer, policy: CalculatorPolicy) -> CalculationContent:
    assert inputs.goal_inr is not None and inputs.months is not None
    rates, example = scenario_values(
        inputs.rates_pct,
        policy.example_rates[CalculatorTool.GOAL],
        policy.bounds["rate_pct"],
        policy,
    )
    saved = inputs.already_saved_inr or 0
    results = finance.goal_contribution(inputs.goal_inr, inputs.months, rates, saved)
    head = _Lines(r)
    head.add("calc.goal.headline", goal=rupees(inputs.goal_inr), months=str(inputs.months))
    scenarios, refs = [], list(head.refs)
    for res in results:
        scenario, s_refs = _scenario(
            r,
            "calc.label.rate",
            {"rate": pct(res.annual_rate_pct)},
            res.annual_rate_pct,
            {"monthly_needed_inr": res.monthly_needed_inr, "invested_inr": res.invested_inr},
            [
                ("calc.goal.line.monthly", {"monthly": rupees(res.monthly_needed_inr)}),
                ("calc.goal.line.invested", {"invested": rupees(res.invested_inr)}),
            ],
        )
        scenarios.append(scenario)
        refs += s_refs
    first, last = results[0], results[-1]
    explanation = r.text(
        "calc.goal.explanation",
        goal=rupees(inputs.goal_inr),
        goal_words=_words(inputs.goal_inr, r),
        months=str(inputs.months),
        first_rate=pct(first.annual_rate_pct),
        first_monthly=rupees(first.monthly_needed_inr),
        last_rate=pct(last.annual_rate_pct),
        last_monthly=rupees(last.monthly_needed_inr),
    )
    keys = ["calc.assumption.illustration"]
    keys += ["calc.assumption.example_rates"] if example else []
    keys += ["calc.assumption.monthly_compounding"]
    slotted: list[tuple[str, dict[str, str]]] = (
        [("calc.goal.assumption.saved", {"saved": rupees(saved)})]
        if saved
        else [("calc.goal.assumption.none_saved", {})]
    )
    slotted.append(("calc.assumption.returns_vary", {}))
    return _content(
        CalculatorTool.GOAL, inputs, rates, head, explanation, keys, slotted, scenarios, refs, r
    )


def _inflation(
    inputs: CalculationInputs, r: Renderer, policy: CalculatorPolicy
) -> CalculationContent:
    assert inputs.amount_inr is not None and inputs.years is not None
    rates, example = scenario_values(
        inputs.rates_pct,
        policy.example_rates[CalculatorTool.INFLATION],
        policy.bounds["inflation_pct"],
        policy,
    )
    results = finance.inflation_purchasing_power(inputs.amount_inr, inputs.years, rates)
    amount = rupees(inputs.amount_inr)
    head = _Lines(r)
    head.add("calc.inflation.headline", amount=amount, years=str(inputs.years))
    scenarios, refs = [], list(head.refs)
    for res in results:
        scenario, s_refs = _scenario(
            r,
            "calc.label.inflation",
            {"rate": pct(res.inflation_pct)},
            res.inflation_pct,
            {"future_cost_inr": res.future_cost_inr, "today_value_inr": res.today_value_inr},
            [
                (
                    "calc.inflation.line.future_cost",
                    {"amount": amount, "future": rupees(res.future_cost_inr)},
                ),
                (
                    "calc.inflation.line.today_value",
                    {"amount": amount, "today": rupees(res.today_value_inr)},
                ),
            ],
        )
        scenarios.append(scenario)
        refs += s_refs
    top = results[-1]
    explanation = r.text(
        "calc.inflation.explanation",
        rate=pct(top.inflation_pct),
        amount=amount,
        amount_words=_words(inputs.amount_inr, r),
        years=str(inputs.years),
        today=rupees(top.today_value_inr),
        today_words=_words(top.today_value_inr, r),
    )
    keys = ["calc.assumption.illustration"]
    keys += ["calc.assumption.example_inflation"] if example else []
    return _content(
        CalculatorTool.INFLATION, inputs, rates, head, explanation, keys, [], scenarios, refs, r
    )


def _consequence(
    inputs: CalculationInputs, r: Renderer, policy: CalculatorPolicy
) -> CalculationContent:
    assert inputs.amount_inr is not None
    drops, example = scenario_values(
        inputs.drops_pct, policy.example_drops, policy.bounds["drop_pct"], policy
    )
    leverage = inputs.leverage or 1.0
    results = finance.consequence(inputs.amount_inr, drops, leverage)
    amount = rupees(inputs.amount_inr)
    head = _Lines(r)
    head.add("calc.consequence.headline", amount=amount)
    scenarios, refs = [], list(head.refs)
    for res in results:
        lines: list[tuple[str, dict[str, str]]] = [
            ("calc.consequence.line.loss", {"loss": rupees(res.loss_inr)})
        ]
        if res.exceeds_amount:
            lines.append(("calc.consequence.line.exceeds", {"extra": rupees(-res.left_inr)}))
        else:
            lines.append(
                ("calc.consequence.line.left", {"amount": amount, "left": rupees(res.left_inr)})
            )
        scenario, s_refs = _scenario(
            r,
            "calc.label.drop",
            {"drop": pct(res.drop_pct)},
            res.drop_pct,
            {"exposure_inr": res.exposure_inr, "loss_inr": res.loss_inr, "left_inr": res.left_inr},
            lines,
        )
        scenarios.append(scenario)
        refs += s_refs
    top = results[-1]
    explanation = r.text(
        "calc.consequence.explanation",
        drop=pct(top.drop_pct),
        exposure=rupees(top.exposure_inr),
        exposure_words=_words(top.exposure_inr, r),
        loss=rupees(top.loss_inr),
    )
    keys = ["calc.assumption.illustration"]
    keys += ["calc.assumption.example_drops"] if example else []
    slotted: list[tuple[str, dict[str, str]]] = (
        [
            (
                "calc.consequence.assumption.leverage",
                {"leverage": pct(leverage), "exposure": rupees(results[0].exposure_inr)},
            )
        ]
        if leverage > 1
        else [("calc.consequence.assumption.no_leverage", {})]
    )
    return _content(
        CalculatorTool.CONSEQUENCE,
        inputs,
        drops,
        head,
        explanation,
        keys,
        slotted,
        scenarios,
        refs,
        r,
    )


def _cost_label(a: finance.CostAssumption) -> tuple[str, dict[str, str]]:
    per_trade = rupees(round(a.per_trade_inr))
    if a.pct_of_value == 0:
        return "calc.label.cost_fixed", {"per_trade": per_trade}
    if a.per_trade_inr == 0:
        return "calc.label.cost_pct", {"pct": pct(a.pct_of_value)}
    return "calc.label.cost_both", {"per_trade": per_trade, "pct": pct(a.pct_of_value)}


def _costs(inputs: CalculationInputs, r: Renderer, policy: CalculatorPolicy) -> CalculationContent:
    assert inputs.trade_value_inr is not None and inputs.trades_per_month is not None
    months = inputs.months or policy.cost_default_months
    results = finance.cost_illustration(
        inputs.trade_value_inr, inputs.trades_per_month, months, list(policy.cost_assumptions)
    )
    trades = results[0].trades
    head = _Lines(r)
    head.add("calc.costs.headline", trades=str(trades), value=rupees(inputs.trade_value_inr))
    scenarios, refs = [], list(head.refs)
    for res in results:
        label_key, label_slots = _cost_label(res.assumption)
        scenario, s_refs = _scenario(
            r,
            label_key,
            label_slots,
            None,
            {"per_trade_cost_inr": res.per_trade_cost_inr, "total_cost_inr": res.total_cost_inr},
            [
                ("calc.costs.line.per_trade", {"per_trade": rupees(res.per_trade_cost_inr)}),
                (
                    "calc.costs.line.total",
                    {"months": str(months), "total": rupees(res.total_cost_inr)},
                ),
            ],
        )
        scenarios.append(scenario)
        refs += s_refs
    totals = sorted(res.total_cost_inr for res in results)
    explanation = r.text(
        "calc.costs.explanation",
        trades=str(trades),
        low_total=rupees(totals[0]),
        high_total=rupees(totals[-1]),
        high_words=_words(totals[-1], r),
    )
    keys = ["calc.assumption.illustration", "calc.costs.assumption.hypothetical"]
    slotted = [("calc.costs.assumption.months", {"months": str(months)})]
    echoed = inputs.model_copy(update={"months": months})
    return _content(
        CalculatorTool.COSTS, echoed, [], head, explanation, keys, slotted, scenarios, refs, r
    )


def _content(
    tool: CalculatorTool,
    inputs: CalculationInputs,
    assumptions_used: list[float],
    head: _Lines,
    explanation: str,
    keys: list[str],
    slotted: list[tuple[str, dict[str, str]]],
    scenarios: list[Scenario],
    refs: list[TemplateRef],
    renderer: Renderer,
) -> CalculationContent:
    notes = _Lines(renderer)
    for key in keys:
        notes.add(key)
    for key, slots in slotted:
        notes.add(key, **slots)
    echoed: dict[str, int | float | list[float]] = {
        k: v
        for k, v in inputs.model_dump(exclude={"tool", "rates_pct", "drops_pct"}).items()
        if v is not None
    }
    if assumptions_used:
        name = "drops_pct" if tool == CalculatorTool.CONSEQUENCE else "rates_pct"
        echoed[name] = assumptions_used
    return CalculationContent(
        tool=tool,
        inputs=echoed,
        headline=head.texts[0],
        explanation=explanation,
        assumptions=notes.texts,
        scenarios=scenarios,
        speak=refs + notes.refs,
    )


BUILDERS: dict[
    CalculatorTool, Callable[[CalculationInputs, Renderer, CalculatorPolicy], CalculationContent]
] = {
    CalculatorTool.SIP: _sip,
    CalculatorTool.GOAL: _goal,
    CalculatorTool.INFLATION: _inflation,
    CalculatorTool.CONSEQUENCE: _consequence,
    CalculatorTool.COSTS: _costs,
}


def build_calculation(inputs: CalculationInputs, renderer: Renderer) -> CalculationContent:
    """Run the chosen tool and render the result.

    Args:
        inputs: Complete inputs (``missing_fields`` returned nothing).
        renderer: Renderer for the user's locale (applies the output validator).

    Returns:
        The rendered calculation content.

    Raises:
        ValueError: If the tool is missing or disabled (callers ask first).
    """
    policy = get_calculator_policy()
    if inputs.tool is None or inputs.tool not in policy.enabled:
        raise ValueError("calculator tool missing or disabled")
    return BUILDERS[inputs.tool](inputs, renderer, policy)
