# Reason codes

Every intervention Ruko shows is explained by one or more reason codes. Codes are
produced by deterministic code (rules, lexicon, link and payment checks) or by the
user's own declarations; the LLM can only *propose* signals, which are merged with
lowered certainty when the lexicon disagrees (Stage 6).

Each code has:

- **Meaning**: what it says, in plain words.
- **Trigger source**: `user` (declared in the profile or form), `rule` (engine arithmetic on the
  user's own numbers and rules), `lexicon` (deterministic pattern match on the message),
  `llm` (extraction, never alone decisive).
- **Severity**: default weight (`low`, `medium`, `high`, `critical`), set in
  `data/policy/intervention.yaml`.
- **Solo level**: the level the code produces on its own (combinations can raise it, see
  `docs/intervention_policy.md`).
- **Template key**: the localized text that explains it (`data/templates/{locale}.yaml`).

Signals are never verdicts. Every code shown to a user carries a certainty label
(`possible`, `likely`, `unclear`).

## Personal rules and money

| Code | Meaning | Trigger source | Severity | Solo level | Template key |
|---|---|---|---|---|---|
| `RULE_MAX_SHARE_EXCEEDED` | This amount is a bigger share of your savings than your own rule allows. | rule (amount vs. savings band / exact, vs. `max_share_of_savings_pct`) | high | L2 | `reason.rule_max_share_exceeded` |
| `RULE_MAX_AMOUNT_EXCEEDED` | This amount is above the maximum you set for one decision. | rule (amount vs. `max_amount_inr`) | high | L2 | `reason.rule_max_amount_exceeded` |
| `BORROWED_FUNDS` | You said this money is borrowed. | user | high | L2 | `reason.borrowed_funds` |
| `PROTECTED_GOAL_FUNDS` | You said this money is set aside for a goal you protected. | user | critical | L3 | `reason.protected_goal_funds` |
| `EMERGENCY_BUFFER_AT_RISK` | You said this is emergency money, or it would leave less than the emergency buffer you set. | user / rule | high | L2 | `reason.emergency_buffer_at_risk` |

## Product, novelty and plan

| Code | Meaning | Trigger source | Severity | Solo level | Template key |
|---|---|---|---|---|---|
| `FIRST_TIME_PRODUCT` | You said you have not used this kind of product before. | user (declared experience) | low | L1 | `reason.first_time_product` |
| `LEVERAGED_PRODUCT` | Small price moves can mean large rupee changes in this product. | rule (product class `derivative`) | low | L0 | `reason.leveraged_product` |
| `NO_EXIT_PLAN` | No exit plan written for a product where losses can grow fast. | user / rule (product class in `exit_plan_required_for`) | medium | L2 | `reason.no_exit_plan` |
| `PLAN_DEVIATION` | This differs from a plan you logged earlier. | rule (event vs. `plans`) | medium | L1 | `reason.plan_deviation` |

## Where it came from

| Code | Meaning | Trigger source | Severity | Solo level | Template key |
|---|---|---|---|---|---|
| `UNSOLICITED_SOURCE` | This came from a group or person you did not ask. | user / lexicon / llm | low | L1 | `reason.unsolicited_source` |

## Pressure and fraud patterns (from the message)

| Code | Meaning | Trigger source | Severity | Solo level | Template key |
|---|---|---|---|---|---|
| `GUARANTEED_RETURN_CLAIM` | The message promises fixed or guaranteed returns. | lexicon / llm | medium | L2 | `reason.guaranteed_return_claim` |
| `URGENCY_PRESSURE` | The message pushes you to act fast or says seats/time are limited. | lexicon / llm | low | L1 | `reason.urgency_pressure` |
| `AUTHORITY_CLAIM` | The message claims registration, certificates or official backing. | lexicon / llm | low | L1 | `reason.authority_claim` |
| `PROFIT_SCREENSHOT_SOCIAL_PROOF` | The message uses others' profit screenshots or testimonials. | lexicon / llm | low | L1 | `reason.profit_screenshot_social_proof` |
| `UNVERIFIED_PLATFORM_LINK` | The link uses a shortener, invite link, APK, IP address, no HTTPS, or a lookalike name. | lexicon (link analyzer, string-only, never fetched) | medium | L2 | `reason.unverified_platform_link` |
| `APP_INSTALL_REQUEST` | The message asks you to install an app or APK. | lexicon / llm | medium | L2 | `reason.app_install_request` |
| `PAY_TO_INDIVIDUAL_ACCOUNT` | You are asked to pay a personal UPI ID or bank account. | lexicon (payment classifier) / llm | critical | L3 | `reason.pay_to_individual_account` |
| `IMPERSONATION_SUSPECTED` | The message seems to pose as a regulator, exchange, depository or known firm. | lexicon / llm | critical | L3 | `reason.impersonation_suspected` |
| `WITHDRAWAL_FEE_DEMAND` | You are asked to pay a fee or "tax" before you can withdraw profits. | lexicon / llm | critical | L3 | `reason.withdrawal_fee_demand` |

## Declared recent behaviour

Ruko cannot see trades. These codes come only from what the user tells it.

| Code | Meaning | Trigger source | Severity | Solo level | Template key |
|---|---|---|---|---|---|
| `POST_LOSS_REENTRY_DECLARED` | You said you recently took a loss. | user | medium | L1 | `reason.post_loss_reentry_declared` |
| `HIGH_FREQUENCY_DECLARED` | You said you have traded many times this week. | user (`trades_this_week` in a high band) | medium | L1 | `reason.high_frequency_declared` |

## Categories used by the policy

| Category | Codes |
|---|---|
| `hard_breach` | `RULE_MAX_SHARE_EXCEEDED`, `RULE_MAX_AMOUNT_EXCEEDED`, `BORROWED_FUNDS`, `EMERGENCY_BUFFER_AT_RISK` |
| `scam_pressure` | `GUARANTEED_RETURN_CLAIM`, `URGENCY_PRESSURE`, `AUTHORITY_CLAIM`, `PROFIT_SCREENSHOT_SOCIAL_PROOF`, `UNVERIFIED_PLATFORM_LINK`, `APP_INSTALL_REQUEST` |
| `scam_strong` | `PAY_TO_INDIVIDUAL_ACCOUNT`, `IMPERSONATION_SUSPECTED`, `WITHDRAWAL_FEE_DEMAND` |
| `novelty` | `FIRST_TIME_PRODUCT` |

The authoritative values live in `data/policy/intervention.yaml`; a test keeps this
document and the YAML in sync (Stage 4).
