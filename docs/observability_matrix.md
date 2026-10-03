# Observability matrix

> Status: **DRAFT — awaiting user review** (v2).

Every signal Ruko uses: which dimension it belongs to, where it comes from now and where it
could come from in production, and whether the prototype can actually see it. Signals that need
broker or bank data are listed so that **Ruko never claims to detect them**.

Sources: `user_declared` (the user says it), `observed_in_ruko` (computed from what the user
shared or from on-device counters), `broker_integration` (an embedding broker sends it through
`/v1/order-intent`), `bank_or_aa` (a bank or Account Aggregator, with consent; not built).

| Signal | Dimension | Prototype source | Production source | In prototype | Reliability | Privacy | Used by |
|---|---|---|---|---|---|---|---|
| Decision stage (learn / evaluate / consider / about to act / already acted) | routing | observed_in_ruko (patterns; LLM fills unknown) or user_declared | same | yes | medium | low | workflow routing |
| Decision amount (₹) | behavioural | user_declared | broker_integration (amount band) | yes | high | medium | rules, exposure numbers, leverage card |
| Funding source (savings / borrowed / emergency / protected goal) | behavioural | user_declared | broker_integration (borrowed flag) | yes | medium | high | `BORROWED_FUNDS`, `EMERGENCY_FUNDS`, `PROTECTED_GOAL_FUNDS` |
| Monthly expenses, liquid savings (bands or exact) | behavioural | user_declared | user_declared; bank_or_aa | yes | medium | high | exposure numbers, `RULE_MAX_SHARE_EXCEEDED`, `EMERGENCY_FUNDS` |
| Own rules (max share, max amount, no borrowing, protected goals, cooling-off) | behavioural | user_declared | user_declared | yes | high | medium | rule checks |
| Experience per product class | behavioural | user_declared | user_declared; broker_integration | yes | medium | low | `FIRST_TIME_PRODUCT` |
| Decision plan (reason, horizon, reconsider condition: presence only) | behavioural | user_declared | user_declared; broker_integration (plan-match flag) | yes | medium | low (words stay on device) | `PLAN_INCOMPLETE`, `UNPLANNED_DECISION` |
| Prior plans (product class, amount range) | behavioural | user_declared | user_declared | yes | high | low | plan relief, `PLAN_DEVIATION` |
| Recent loss; trades this week (band) | behavioural | user_declared | broker_integration | yes (self-report) | low | medium | `POST_LOSS_REENTRY_DECLARED`, `HIGH_FREQUENCY_DECLARED` |
| Product class, action, holding intent | behavioural (context) | observed_in_ruko (lexicon + LLM) or user_declared | broker_integration | yes | medium | low | leverage, plan expectation, cost and tax cards |
| Age band (optional) | behavioural (context) | user_declared | user_declared | yes | high | medium | base-rate card |
| Source type (group, known person, influencer, own research) | content | observed_in_ruko or user_declared | same | yes | medium | low | `UNSOLICITED_SOURCE` |
| Red-flag language (guaranteed returns, urgency, authority, social proof, app install, withdrawal fee, impersonation) | content | observed_in_ruko (lexicon; LLM at reduced certainty) | same | yes | medium | low after redaction | content signals, cards |
| Payment destination in text (phone UPI ID, other UPI ID, bank details, QR, `@valid` pattern) | content | observed_in_ruko (payment classifier on redacted placeholders) | same | yes | medium | high (redacted first) | `PAY_TO_INDIVIDUAL_ACCOUNT`, recovery pre-fill |
| Link features (shortener, invite, APK, IP host, no HTTPS, lookalike) | content | observed_in_ruko (string only, never fetched) | same | yes | medium | low | `UNVERIFIED_PLATFORM_LINK`, `IMPERSONATION_SUSPECTED` |
| Language and script | routing | observed_in_ruko | same | yes | medium | low | rendering, voice |
| Interventions shown this week; rule-following streak; seen cards | behavioural (counters) | observed_in_ruko (device) | same | yes | high | low | attention budget, decay, card fading |
| Journal entries (decision, overrides and reasons, plan followed, comprehension) | impact | user_declared, sent per request | same | yes | medium | medium | journal review (`docs/impact_metrics.md`) |
| Actual trade history and order frequency | behavioural | — | broker_integration | **no** | — | high | not used |
| Rapid loss-chasing / revenge trading / late-night trading | behavioural | — | broker_integration | **no** | — | high | not used; only the user's own declaration of a recent loss |
| Actual P&L and margin / leverage used | behavioural | — | broker_integration | **no** | — | high | not used |
| Whether money was actually paid, and to whom | content | — | bank_or_aa | **no** | — | high | not used; the user answers recovery questions |
| Whether a UPI ID is truly a SEBI-registered intermediary | content | — | SEBI Check / NPCI | **no** | — | low | not used; Ruko notes only the `@valid` *pattern* and points to SEBI Check |
| Account balances | behavioural | — | bank_or_aa | **no** | — | high | not used |

## What Ruko will say about these limits

- "Ruko cannot see your trades or your bank account. It only knows what you tell it and what
  you share with it."
- "A handle that looks like `@valid` is a pattern check, not a verification. Use SEBI's own
  check before paying."
