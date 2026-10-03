# Observability matrix

> Status: **draft, awaiting the repo owner's approval** (BUILD_PLAN Stage 1).

Every signal Ruko uses, where it comes from, and whether the prototype can actually see
it. Signals that need broker or bank data are listed so that **Ruko never claims to detect
them**. In the prototype they are either absent or replaced by a user declaration.

Source values:
- `user_declared`: the user tells Ruko (profile, form, or answer to a question).
- `observed_in_ruko`: computed from what the user shared with Ruko or from on-device counters.
- `requires_broker_or_bank_data`: needs trade, account or payment records Ruko does not have.

| Signal | Source | In prototype | Reliability | Privacy sensitivity | Used by |
|---|---|---|---|---|---|
| Decision amount (₹) | user_declared | yes | high (user's own figure) | medium | engine rule (max amount, share, buffer), cards (leverage rupees) |
| Funding source (savings / borrowed / emergency / protected goal) | user_declared | yes | medium (honesty-dependent) | high | engine rule (`BORROWED_FUNDS`, `EMERGENCY_BUFFER_AT_RISK`, `PROTECTED_GOAL_FUNDS`) |
| Monthly expenses (band or exact) | user_declared | yes | medium (bands) | high | engine metrics (months of expenses, buffer) |
| Liquid savings (band or exact) | user_declared | yes | medium (bands) | high | engine metrics (share of savings), rule `RULE_MAX_SHARE_EXCEEDED` |
| Emergency buffer target (months) | user_declared | yes | high | low | engine rule `EMERGENCY_BUFFER_AT_RISK` |
| Personal rules (max share, max amount, no borrowing, protected goals, cooling-off) | user_declared | yes | high | medium | engine rules |
| Experience per product class | user_declared | yes | medium | low | engine novelty (`FIRST_TIME_PRODUCT`) |
| Age band | user_declared (optional) | yes | high | medium | base-rate card (SEBI group statistic by age band) |
| Logged plan (product, amount range, exit rule) | user_declared | yes | high | low | engine plan matching (`PLAN_DEVIATION`, plan relief) |
| Exit plan for this decision | user_declared | yes | medium | low | engine rule `NO_EXIT_PLAN` |
| Recent loss | user_declared | yes | low (self-report) | medium | engine `POST_LOSS_REENTRY_DECLARED` |
| Trades this week (band) | user_declared | yes | low (self-report) | low | engine `HIGH_FREQUENCY_DECLARED`, cost card |
| Product class (cash equity, derivative, IPO, MF, scheme/app, crypto) | observed_in_ruko (LLM + lexicon) or user_declared | yes | medium | low | engine (leverage, exit plan), cards |
| Source type (group, known person, influencer, own research) | observed_in_ruko or user_declared | yes | medium | low | engine `UNSOLICITED_SOURCE` |
| Red-flag language (guaranteed returns, urgency, authority claims, profit screenshots, app install, withdrawal fee) | observed_in_ruko (lexicon, LLM) | yes | medium (pattern-based; certainty-labelled) | low after redaction | engine signals, cards |
| Payment destination in text (personal UPI ID, bank details in chat, QR mention, `@valid` handle pattern) | observed_in_ruko (payment classifier) | yes | medium | high (redacted before any external call) | engine `PAY_TO_INDIVIDUAL_ACCOUNT`, cards, recovery |
| Link features (shortener, invite link, APK, IP host, no HTTPS, lookalike domain) | observed_in_ruko (string analysis only, never fetched) | yes | medium | low | engine `UNVERIFIED_PLATFORM_LINK` |
| Impersonation cues (regulator / depository / exchange names with odd domains or contact routes) | observed_in_ruko | yes | low–medium | low | engine `IMPERSONATION_SUSPECTED` |
| Language and script | observed_in_ruko | yes | medium (code-mixed is harder) | low | rendering, voice |
| Interventions shown this week | observed_in_ruko (device counter) | yes | high | low | attention budget |
| Rule-following streak | observed_in_ruko (device journal) | yes | medium (depends on journaling) | low | friction decay |
| Seen cards | observed_in_ruko (device) | yes | high | low | card fading |
| Journal entries (decision, overrides, exit plan followed, outcome) | user_declared, sent per request | yes | medium | medium | journal review |
| Actual trade history and order frequency | requires_broker_or_bank_data | **no** | — | high | not used; future broker embedding |
| Rapid loss-chasing / revenge trading | requires_broker_or_bank_data | **no** | — | high | not used; Ruko only uses the user's own declaration of a recent loss |
| Actual P&L and margin / leverage used | requires_broker_or_bank_data | **no** | — | high | not used |
| Whether money was actually paid, and to whom (KYC of the payee) | requires_broker_or_bank_data | **no** | — | high | not used; the user answers recovery questions instead |
| Whether a UPI ID or account is truly a SEBI-registered intermediary | requires_broker_or_bank_data (SEBI Check / NPCI) | **no** | — | low | not used; Ruko only notes whether the handle has the `@valid` *pattern* and points the user to SEBI's own check |
| Account balances | requires_broker_or_bank_data | **no** | — | high | not used |

## What Ruko will say about these limits

- "Ruko cannot see your trades or your bank account. It only knows what you tell it and what
  you share with it."
- "A handle that looks like `@valid` is a pattern check, not a verification. Use SEBI's own
  check before paying."
