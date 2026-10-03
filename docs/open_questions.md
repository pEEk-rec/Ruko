# Open questions

Decisions the plan did not cover. Per CLAUDE.md 4.3, each took the most conservative reasonable
default (quieter, safer, simpler), and the alternative is recorded so the owner can switch.
Most are one-line changes in a data file.

## Engine and levels

| # | Question | Default chosen | Alternative | Where to change |
|---|---|---|---|---|
| 1 | Does "two or more rule breaches" (L3) count borrowed / emergency money? | Yes: any 2 of max-share, max-amount, borrowed, emergency | Only the user's own written rules count | `level_rules.multiple_rule_breaches` in `data/policy/intervention.yaml` |
| 2 | One medium content signal alone (e.g. a guaranteed-return claim) | L1 (the v2 table puts it at L2 only with a behavioural trigger or a second medium signal) | L2 | add a level rule |
| 3 | Several low content signals together | Never above L1 ("a single low signal never alarms"; extended to several) | Two lows → L2 | add a level rule |
| 4 | Recent loss + leverage, or high frequency + leverage | L1 (v1 had L2; not in the v2 table) | L2 combination rules | add rules |
| 5 | Where is a decision plan expected? | Derivatives and crypto only (`UNPLANNED_DECISION` / `PLAN_INCOMPLETE` elsewhere would nudge every ordinary decision) | All product classes | `params.plan_expected_for` |
| 6 | When is the "already paid?" recovery entry shown? | When message signals alone reach L3 | From L2 | `params.recovery_min_content_level` |
| 7 | An LLM-only high-severity signal at `unclear` certainty | Still counts for L3 (certainty never hides fraud), and the user sees "Unclear"; evidence must be a verbatim quote | Exclude `unclear` LLM-only signals from escalation | `engine/levels.py` |
| 8 | Policy numbers (L1 budget 3/week, decay streak 5, default cooling-off 15 min, 10/25/50% illustrations) | Proposals | Owner's numbers | `params` |

## Stages and routing

| # | Question | Default chosen | Alternative |
|---|---|---|---|
| 9 | A forwarded tip or offer with no note from the user | `consider_action` (the share happens at the moment of deciding) | `evaluate_content`, or ask |
| 10 | `already_acted` together with acting words | Ask (`unknown`) | Recovery first |
| 11 | High-severity content signal while amount/funding are missing | Show the warning at once, no questions first | Ask first |
| 12 | Text pre-fill of recovery answers (paid? how? app?) | Yes, yes/no facts and payment method only; user can correct via `/v1/recover` | Always ask |
| 13 | Content report shows a level? | No: signals with severity and certainty only (a level reads like a verdict) | Show the content-dimension level |

## Facts and production

| # | Question | Default chosen | Alternative |
|---|---|---|---|
| 14 | Production hides unverified facts (CLAUDE.md 3); this also hides 1930 and the portals until verified | Hide (literal rule) | Exempt safety-critical recovery routes |
| 15 | Glossary entries cite the SEBI investor website home page | Generic pointer, TODO_VERIFY specific pages | Link each term's page |
| 16 | Capital-gains card | Only when the action is selling; hidden in production until verified | Never show tax |

## Privacy and providers

| # | Question | Default chosen | Alternative |
|---|---|---|---|
| 17 | Screenshots and voice notes reach the OCR / STT provider unredacted | Accepted for the prototype, documented | On-device OCR / STT, send only text |
| 18 | Gemini free tier (5 requests/minute) | Keep; lexicon fallback covers outages | Paid tier or lighter model |
| 19 | Rate limiter is in memory, per process | Fine for one instance | Shared store for several instances |
| 20 | Settings loader | Own 10-line loader (no `pydantic-settings`, which is pre-approved but unnecessary) | Switch to `pydantic-settings` |

## Guardrails

| # | Question | Default chosen | Alternative |
|---|---|---|---|
| 21 | Shared text that tells an "assistant" to act as an adviser (eval `inj-en-03`) | Refused as `ROLEPLAY_ADVISOR` (over-refusal is the safe side) | Analyze as content |
| 22 | Deterministic gate coverage on unseen phrasing | Held-out baseline was 6/16 before generalisation; LLM second opinion adds refusals when configured | Require the LLM classifier in production |

## Process

| # | Question | Default chosen |
|---|---|---|
| 23 | The same author wrote the patterns and both evaluation splits | Stated in the report; a truly blind test set needs other people's messages |
| 24 | The stage 6-12 work was committed as one commit (shared files made per-stage commits inconsistent) | Owner approved committing; split was not possible without breaking intermediate states |
