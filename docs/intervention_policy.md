# Intervention policy

The safety engine turns a `DecisionEvent` and a `UserProfile` into a level from L0 to L3.
It is deterministic code with every threshold in `data/policy/intervention.yaml`. The
LLM never decides a level. Every level can be overridden by the user; overrides are
recorded in the journal on the device.

## The four levels

| Level | Name | What the user sees |
|---|---|---|
| L0 | Silent | Nothing, or a quiet "logged" tick. Routine decisions pass. |
| L1 | Nudge | One line and one reflection question. |
| L2 | Speed bump | Your numbers, your rules, signals with certainty, one question, up to 3 cards. |
| L3 | Cooling-off / strong warning | As L2, plus a suggested wait, and for fraud patterns the "already paid?" recovery entry. |

## How the level is chosen

1. **Collect reasons.** The engine gathers reason codes from the user's declarations, the
   rule checks on their own numbers, plan matching, and the message signals.
2. **Solo levels.** Each code has a level it produces on its own (see the table below and
   `docs/reason_codes.md`). The starting level is the highest solo level present, or L0
   if there are no codes.
3. **Combination rules.** Some combinations raise the level further. The final computed
   level is the highest of the solo levels and all matching combination rules. Adding a
   reason can therefore never lower the level.
4. **Plan relief.** If the decision matches a plan the user logged in advance (same
   product class, amount inside the planned range), `FIRST_TIME_PRODUCT` and `NO_EXIT_PLAN`
   are not raised: the user already thought this through while calm. If a plan for the same
   product class exists but the amount is outside it, `PLAN_DEVIATION` is raised.
5. **Friction decay.** If the only reason is novelty (`FIRST_TIME_PRODUCT`) and the user's
   streak of rule-following decisions is at least the threshold, L1 becomes L0.
6. **Attention budget.** If the level is L1, every reason is low severity, and the user has
   already seen the weekly maximum of L1 nudges, the nudge is silenced (L0). L1 nudges with
   medium reasons, and every L2 and L3, are never silenced by the budget.
7. **Cooling-off and recovery.** At L2 and above, the user's own cooling-off rule is shown if
   they set one; at L3 without a user rule, the policy default is suggested. If any
   fraud-pattern reason is present at L2 or above, the recovery entry point is included.

## Solo levels

| Code | Severity | Solo level |
|---|---|---|
<!-- solo-table:start -->
| `RULE_MAX_SHARE_EXCEEDED` | high | L2 |
| `RULE_MAX_AMOUNT_EXCEEDED` | high | L2 |
| `BORROWED_FUNDS` | high | L2 |
| `PROTECTED_GOAL_FUNDS` | critical | L3 |
| `EMERGENCY_BUFFER_AT_RISK` | high | L2 |
| `FIRST_TIME_PRODUCT` | low | L1 |
| `LEVERAGED_PRODUCT` | low | L0 |
| `NO_EXIT_PLAN` | medium | L2 |
| `PLAN_DEVIATION` | medium | L1 |
| `UNSOLICITED_SOURCE` | low | L1 |
| `GUARANTEED_RETURN_CLAIM` | medium | L2 |
| `URGENCY_PRESSURE` | low | L1 |
| `AUTHORITY_CLAIM` | low | L1 |
| `PROFIT_SCREENSHOT_SOCIAL_PROOF` | low | L1 |
| `PAY_TO_INDIVIDUAL_ACCOUNT` | critical | L3 |
| `UNVERIFIED_PLATFORM_LINK` | medium | L2 |
| `IMPERSONATION_SUSPECTED` | critical | L3 |
| `APP_INSTALL_REQUEST` | medium | L2 |
| `WITHDRAWAL_FEE_DEMAND` | critical | L3 |
| `POST_LOSS_REENTRY_DECLARED` | medium | L1 |
| `HIGH_FREQUENCY_DECLARED` | medium | L1 |
<!-- solo-table:end -->

## Combination rules

| Rule | When | Level |
|---|---|---|
<!-- combo-table:start -->
| `multiple_hard_breaches` | at least 2 of: `RULE_MAX_SHARE_EXCEEDED`, `RULE_MAX_AMOUNT_EXCEEDED`, `BORROWED_FUNDS`, `EMERGENCY_BUFFER_AT_RISK` | L3 |
| `many_pressure_signals` | at least 3 of: `GUARANTEED_RETURN_CLAIM`, `URGENCY_PRESSURE`, `AUTHORITY_CLAIM`, `PROFIT_SCREENSHOT_SOCIAL_PROOF`, `UNVERIFIED_PLATFORM_LINK`, `APP_INSTALL_REQUEST` | L3 |
| `some_pressure_signals` | at least 2 of: `GUARANTEED_RETURN_CLAIM`, `URGENCY_PRESSURE`, `AUTHORITY_CLAIM`, `PROFIT_SCREENSHOT_SOCIAL_PROOF`, `UNVERIFIED_PLATFORM_LINK`, `APP_INSTALL_REQUEST` | L2 |
| `first_time_leverage` | all of: `FIRST_TIME_PRODUCT`, `LEVERAGED_PRODUCT` | L2 |
| `post_loss_leverage` | all of: `POST_LOSS_REENTRY_DECLARED`, `LEVERAGED_PRODUCT` | L2 |
| `high_frequency_leverage` | all of: `HIGH_FREQUENCY_DECLARED`, `LEVERAGED_PRODUCT` | L2 |
<!-- combo-table:end -->

## Thresholds and defaults

<!-- params-table:start -->
| Parameter | Value |
|---|---|
| `l1_budget_per_week` | 3 |
| `decay_streak_threshold` | 5 |
| `l3_default_cooling_off_minutes` | 15 |
| `exit_plan_required_for` | derivative, crypto |
| `leveraged_product_classes` | derivative |
| `high_frequency_bands` | gt_20 |
| `adverse_move_illustrations_pct` | 10, 25, 50 |
<!-- params-table:end -->

## Things the policy deliberately does not do

- It never blocks. `override_allowed` is always `true` in the response contract.
- It never uses certainty to *hide* a fraud pattern: a `possible` withdrawal-fee demand still
  gives L3, but the user sees the word "possible".
- It never judges the tip, the stock, the scheme or the person who sent it. It only looks at
  the user's own money, rules and plan, and at patterns in the message.
- It never infers the amount or the funding source; if they are missing and needed, Ruko asks.
- It does not claim to detect behaviour that needs broker or bank data (see
  `docs/observability_matrix.md`).
