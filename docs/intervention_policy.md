# Intervention policy

The safety engine turns a `DecisionEvent` and a `UserProfile` into a level from L0 to L3.
It is deterministic code with every threshold in `data/policy/intervention.yaml`; a test
keeps the tables below identical to the YAML. The LLM never decides a level. Every level
can be overridden by the user; overrides are recorded in the journal on the device.

The engine runs only for the decision stages `consider_action` and `about_to_act`
(see `docs/decision_stages.md`). `learn`, `evaluate_content` and `already_acted` take
other paths and never produce a pause.

## The four levels

| Level | Name | What the user sees |
|---|---|---|
| L0 | Pass (silent) | Nothing, or a quiet "noted". Ordinary decisions pass. |
| L1 | Nudge | One line and one reflection question. |
| L2 | Pause | Exposure in the user's rupees, their own rules, every reason with its certainty, one question, up to 3 cards. |
| L3 | Strong pause | As L2, plus a suggested wait; when message signals alone reach L3, the "already paid?" recovery entry. |

## Two independent dimensions

- **Content signals**: what is happening in the message (fraud markers, pressure,
  impersonation, payment-destination red flags). Each has a severity tier (`low`,
  `medium`, `high`) and a certainty (`possible`, `likely`, `unclear`).
- **Behavioural context**: what this decision means for this user (their own rules,
  protected goals, borrowed or emergency money, novelty, decision-plan completeness,
  deviation from a prior plan, declared recent behaviour).

They are never collapsed into one score. The response shows the level each dimension
reaches on its own (`dimension_levels`), the reason codes per dimension, and the IDs of the
level rules that matched.

## Reason codes

| Code | Dimension | Severity | Category |
|---|---|---|---|
<!-- codes-table:start -->
| `RULE_MAX_SHARE_EXCEEDED` | behavioural | high | rule_breach |
| `RULE_MAX_AMOUNT_EXCEEDED` | behavioural | high | rule_breach |
| `BORROWED_FUNDS` | behavioural | high | risky_funds |
| `EMERGENCY_FUNDS` | behavioural | high | risky_funds |
| `PROTECTED_GOAL_FUNDS` | behavioural | high | protected_funds |
| `FIRST_TIME_PRODUCT` | behavioural | low | novelty |
| `LEVERAGED_PRODUCT` | behavioural | low | product_info |
| `PLAN_INCOMPLETE` | behavioural | low | plan |
| `PLAN_DEVIATION` | behavioural | low | plan |
| `UNPLANNED_DECISION` | behavioural | low | plan |
| `POST_LOSS_REENTRY_DECLARED` | behavioural | medium | declared_context |
| `HIGH_FREQUENCY_DECLARED` | behavioural | medium | declared_context |
| `LATE_NIGHT_DECISION` | behavioural | low | timing |
| `UNSOLICITED_SOURCE` | content | low | content |
| `URGENCY_PRESSURE` | content | low | content |
| `AUTHORITY_CLAIM` | content | medium | content |
| `PROFIT_SCREENSHOT_SOCIAL_PROOF` | content | medium | content |
| `GUARANTEED_RETURN_CLAIM` | content | medium | content |
| `APP_INSTALL_REQUEST` | content | medium | content |
| `UNVERIFIED_PLATFORM_LINK` | content | medium | content |
| `IMPERSONATION_SUSPECTED` | content | high | content |
| `PAY_TO_INDIVIDUAL_ACCOUNT` | content | high | content |
| `WITHDRAWAL_FEE_DEMAND` | content | high | content |
<!-- codes-table:end -->

## Level rules

The level is the highest level of all rules that match (L0 if none). Because it is a
maximum, adding a reason can never lower it. A rule that looks only at content signals
also sets the content dimension's level; a rule that looks only at behavioural reasons
sets the behavioural dimension's level.

| Rule | When | Level |
|---|---|---|
<!-- rules-table:start -->
| `low_content_signal` | at least 1 content signal of severity low or higher | L1 |
| `mild_behavioural_trigger` | a behavioural reason in: declared_context, novelty, plan | L1 |
| `rule_breached` | a behavioural reason in: rule_breach | L2 |
| `borrowed_or_emergency_funds` | a behavioural reason in: risky_funds | L2 |
| `first_time_leveraged` | all of: `FIRST_TIME_PRODUCT`, `LEVERAGED_PRODUCT` | L2 |
| `medium_content_with_trigger` | at least 1 content signal of severity medium or higher AND any behavioural trigger | L2 |
| `two_medium_content` | at least 2 different content signals of severity medium or higher | L2 |
| `high_content_signal` | at least 1 content signal of severity high or higher | L3 |
| `protected_goal_funds` | a behavioural reason in: protected_funds | L3 |
| `multiple_rule_breaches` | at least 2 reasons in: risky_funds, rule_breach | L3 |
| `three_medium_content` | at least 3 different content signals of severity medium or higher | L3 |
<!-- rules-table:end -->

In words:

- **L0 pass:** no behavioural triggers and no content signals.
- **L1 nudge:** low content signals only, or one medium content signal alone, or a mild
  behavioural trigger (first time with a product class, no or incomplete decision plan where
  one is expected, a deviation from a prior plan, a declared recent loss or high frequency).
  Low content signals never escalate beyond L1 on their own, however many there are.
- **L2 pause:** a broken personal rule; borrowed or emergency money; a first-time leveraged
  product; a medium content signal together with any behavioural trigger; or two different
  medium content signals.
- **L3 strong pause:** any high-severity content signal; protected-goal money; two or more
  rule breaches (counting borrowed and emergency money); three or more different medium
  content signals.

## After the level

1. **Plan relief.** A decision that fits a plan the user logged in advance (same product class,
   amount inside the planned range), or that the device says follows one, raises no plan
   reason and no novelty reason.
2. **Friction decay.** If the level is L1, there are no content signals, and every behavioural
   trigger is novelty, a rule-following streak at or above the threshold makes it L0.
3. **Attention budget.** If the level is L1, every reason is low severity, and the user has
   already seen the weekly maximum of L1 nudges, the nudge is silenced (L0). L2 and L3 are
   never silenced.
4. **Cooling-off and recovery.** At L2 and above, the user's own cooling-off rule is shown if
   they set one; at L3 without a user rule, the policy default is suggested. When message
   signals alone reach `recovery_min_content_level`, the recovery entry point is included.

## Parameters

<!-- params-table:start -->
| Parameter | Value |
|---|---|
| `l1_budget_per_week` | 3 |
| `decay_streak_threshold` | 5 |
| `l3_default_cooling_off_minutes` | 15 |
| `plan_expected_for` | derivative, crypto |
| `leveraged_product_classes` | derivative |
| `high_frequency_bands` | gt_20 |
| `adverse_move_illustrations_pct` | 10, 25, 50 |
| `behavioural_trigger_categories` | rule_breach, risky_funds, protected_funds, novelty, plan, declared_context, timing |
| `recovery_min_content_level` | L3 |
| `decay_categories` | novelty |
<!-- params-table:end -->

## Things the policy deliberately does not do

- It never blocks. `override_allowed` is always `true`.
- It never uses certainty to *hide* a fraud pattern: a `possible` withdrawal-fee demand still
  gives L3, and the user sees the word "possible".
- It never judges the tip, the stock, the scheme or the person who sent it.
- It never infers the amount or the funding source, and it never says how much a user "can
  afford to lose": exposure is shown only against the user's own stated figures and rules.
- It does not claim to detect behaviour that needs broker or bank data
  (see `docs/observability_matrix.md`).
