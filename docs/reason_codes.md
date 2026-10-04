# Reason codes

Every intervention Ruko shows is explained by one or more reason codes, in two independent
dimensions (see `principles.md`):

- **content**: what is happening in the message (produced by the lexicon, the link analyzer,
  the payment classifier, or proposed by the LLM at reduced certainty)
- **behavioural**: what this decision means for this user (produced by rules on the user's own
  figures, or declared by the user)

Each code has a meaning, a dimension, a severity tier, a trigger source and the template key
that explains it. Severity tiers and categories live in `data/policy/intervention.yaml`; a test
keeps this table and the YAML in sync. Every code shown to a user carries a certainty label
(`possible`, `likely`, `unclear`). Signals are never verdicts.

Trigger sources: `user` (declared in the profile or an answer), `rule` (arithmetic on the user's
own figures or a structural check), `lexicon` (deterministic pattern), `llm` (extraction,
never decisive alone; lowered one certainty step unless the lexicon corroborates).

## Behavioural context

| Code | Meaning | Dimension | Severity | Trigger source | Template key |
|---|---|---|---|---|---|
| `RULE_MAX_SHARE_EXCEEDED` | This amount is a bigger share of your savings than your own rule allows. | behavioural | high | rule | `reason.rule_max_share_exceeded` |
| `RULE_MAX_AMOUNT_EXCEEDED` | This amount is above the maximum you set for one decision. | behavioural | high | rule | `reason.rule_max_amount_exceeded` |
| `BORROWED_FUNDS` | You said this money is borrowed. | behavioural | high | user | `reason.borrowed_funds` |
| `EMERGENCY_FUNDS` | You said this is emergency money, or it would leave less than the buffer you set. | behavioural | high | user / rule | `reason.emergency_funds` |
| `PROTECTED_GOAL_FUNDS` | You said this money is set aside for a goal you protected. | behavioural | high | user | `reason.protected_goal_funds` |
| `FIRST_TIME_PRODUCT` | You said you have not used this kind of product before. | behavioural | low | user | `reason.first_time_product` |
| `LEVERAGED_PRODUCT` | Small price moves can mean large rupee changes in this product. | behavioural | low | rule | `reason.leveraged_product` |
| `PLAN_INCOMPLETE` | Your decision plan lacks a reason, a horizon or a reconsider point. | behavioural | low | user | `reason.plan_incomplete` |
| `PLAN_DEVIATION` | This differs from a plan you logged earlier. | behavioural | low | rule | `reason.plan_deviation` |
| `UNPLANNED_DECISION` | No plan yet for a product where one is expected (derivatives, crypto). | behavioural | low | user | `reason.unplanned_decision` |
| `POST_LOSS_REENTRY_DECLARED` | You said you recently took a loss. | behavioural | medium | user | `reason.post_loss_reentry_declared` |
| `HIGH_FREQUENCY_DECLARED` | You said you have traded many times this week. | behavioural | medium | user | `reason.high_frequency_declared` |
| `LATE_NIGHT_DECISION` | It is late at night where you are, and a decision can look different in the morning. | behavioural | low | rule (device clock) | `reason.late_night_decision` |

Ruko cannot see trades or bank accounts. Loss and frequency codes come only from what the user
declares; it never claims to detect loss-chasing. `LATE_NIGHT_DECISION` is a clock fact (the
device sends only a yes/no for "late at night where you are"); it says nothing about what the
person is doing and never raises a level on its own.

## Content signals

| Code | Meaning | Dimension | Severity | Trigger source | Template key |
|---|---|---|---|---|---|
| `UNSOLICITED_SOURCE` | This came from a group or person you did not ask. | content | low | user / lexicon / llm | `reason.unsolicited_source` |
| `URGENCY_PRESSURE` | The message pushes you to act fast; time or seats are "limited". | content | low | lexicon / llm | `reason.urgency_pressure` |
| `AUTHORITY_CLAIM` | The message claims registration, certificates or official backing. | content | medium | lexicon / llm | `reason.authority_claim` |
| `PROFIT_SCREENSHOT_SOCIAL_PROOF` | The message uses others' profit screenshots or testimonials. | content | medium | lexicon / llm | `reason.profit_screenshot_social_proof` |
| `GUARANTEED_RETURN_CLAIM` | The message contains a guaranteed or fixed-return claim. | content | medium | lexicon / llm | `reason.guaranteed_return_claim` |
| `APP_INSTALL_REQUEST` | The message asks you to install an app, an APK or a screen-sharing tool. | content | medium | lexicon (incl. link analyzer) / llm | `reason.app_install_request` |
| `UNVERIFIED_PLATFORM_LINK` | The link uses a shortener, invite link, APK, IP address, no HTTPS, or a lookalike name. | content | medium | rule (link analyzer, string-only, never fetched) | `reason.unverified_platform_link` |
| `IMPERSONATION_SUSPECTED` | The message seems to pose as a regulator, exchange, depository or known firm. | content | high | lexicon / rule (lookalike link) / llm | `reason.impersonation_suspected` |
| `PAY_TO_INDIVIDUAL_ACCOUNT` | You are asked to pay a personal UPI ID or bank account. | content | high | rule (payment classifier) / lexicon / llm | `reason.pay_to_individual_account` |
| `WITHDRAWAL_FEE_DEMAND` | You are asked to pay a fee or "tax" before you can withdraw. | content | high | lexicon / llm | `reason.withdrawal_fee_demand` |

## How codes become a level

See `docs/intervention_policy.md` for the level rules. In short: a single low content signal
never produces more than a nudge; any high content signal or protected-goal money produces the
strongest pause; everything in between is a documented rule in the YAML.
