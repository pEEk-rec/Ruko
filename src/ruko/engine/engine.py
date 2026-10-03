"""The deterministic safety engine: ``decide(event, profile) -> InterventionDecision``.

Pure function: no I/O, no LLM, no randomness. Every threshold comes from
``data/policy/intervention.yaml``. Steps:

1. Personal numbers (metrics).
2. Reasons: message signals + user's rules + declared context + event fields +
   novelty / leverage + plan matching (with plan relief) + exit plan.
3. One reason per code, keeping the strongest certainty.
4. Level = max(solo levels, combination rules); then friction decay; then attention budget.
5. Cooling-off suggestion, recovery entry, base rate.
"""

from __future__ import annotations

from ruko.engine.attention import apply_attention_budget
from ruko.engine.base_rates import select_base_rate
from ruko.engine.context import declared_context_signals, event_field_signals
from ruko.engine.decay import apply_decay
from ruko.engine.levels import compute_level
from ruko.engine.metrics import compute_numbers
from ruko.engine.novelty import first_time_signal, leverage_signal
from ruko.engine.plan import PlanMatch, deviation_signal, exit_plan_signal, match_plan
from ruko.engine.policy import InterventionPolicy, get_intervention_policy
from ruko.engine.rules import evaluate_rules
from ruko.models.common import Certainty, InterventionLevel, ReasonCode
from ruko.models.decision import ComputedNumbers, InterventionDecision, Reason
from ruko.models.event import DecisionEvent, Signal
from ruko.models.profile import UserProfile

_CERTAINTY_STRENGTH = {Certainty.LIKELY: 2, Certainty.POSSIBLE: 1, Certainty.UNCLEAR: 0}


def collect_signals(
    event: DecisionEvent,
    profile: UserProfile,
    numbers: ComputedNumbers,
    policy: InterventionPolicy,
) -> tuple[list[Signal], PlanMatch]:
    """Gather every signal for this decision.

    Personal-rule, novelty and plan checks only run when the content is a financial
    decision; fraud-pattern signals from the message always count.
    """
    signals = list(event.signals) + event_field_signals(event)
    if not event.is_financial_decision:
        return signals, PlanMatch(None, False)
    signals += evaluate_rules(event, profile, numbers)
    signals += declared_context_signals(profile, policy)
    plan_match = match_plan(event, profile.plans)
    extras = [
        leverage_signal(event, policy),
        None if plan_match.plan else first_time_signal(event, profile),
        deviation_signal(plan_match),
        exit_plan_signal(event, plan_match, policy),
    ]
    signals += [s for s in extras if s is not None]
    return signals, plan_match


def merge_reasons(signals: list[Signal], policy: InterventionPolicy) -> list[Reason]:
    """Keep one reason per code (strongest certainty), ordered most severe first."""
    best: dict[ReasonCode, Signal] = {}
    for signal in signals:
        current = best.get(signal.code)
        if current is None or (
            _CERTAINTY_STRENGTH[signal.certainty] > _CERTAINTY_STRENGTH[current.certainty]
        ):
            best[signal.code] = signal
    order = list(policy.codes)
    reasons = [
        Reason(
            code=s.code, severity=policy.severity(s.code), certainty=s.certainty, source=s.source
        )
        for s in best.values()
    ]
    return sorted(reasons, key=lambda r: (-r.severity.rank, order.index(r.code)))


def _cooling_off(
    level: InterventionLevel, profile: UserProfile, policy: InterventionPolicy
) -> int | None:
    if level.rank < 2:
        return None
    if profile.rules.cooling_off_minutes:
        return profile.rules.cooling_off_minutes
    return policy.l3_default_cooling_off_minutes if level == InterventionLevel.L3 else None


def decide(
    event: DecisionEvent, profile: UserProfile, policy: InterventionPolicy | None = None
) -> InterventionDecision:
    """Decide the intervention level and its reasons for one decision.

    Args:
        event: The structured decision.
        profile: The device snapshot (rules, bands, plans, counters).
        policy: Optional policy override (defaults to the data file).

    Returns:
        The ``InterventionDecision``. ``override_allowed`` is always true.
    """
    policy = policy or get_intervention_policy()
    numbers = compute_numbers(event, profile, policy)
    signals, plan_match = collect_signals(event, profile, numbers, policy)
    reasons = merge_reasons(signals, policy)
    codes = {r.code for r in reasons}

    computed = compute_level(codes, policy)
    level, decayed = apply_decay(computed, codes, profile.attention.rule_following_streak, policy)
    level, attention = apply_attention_budget(level, reasons, profile.attention, policy)

    recovery_codes = policy.codes_in(policy.recovery_categories)
    return InterventionDecision(
        level=level,
        computed_level=computed,
        reasons=reasons,
        numbers=numbers,
        attention=attention,
        decay_applied=decayed,
        matched_plan_id=plan_match.plan.id if plan_match.plan else None,
        cooling_off_minutes=_cooling_off(level, profile, policy),
        recovery_entry=level.rank >= 2 and bool(codes & recovery_codes),
        base_rate=select_base_rate(event, profile) if event.is_financial_decision else None,
        policy_version=policy.version,
    )
