# Open questions and the defaults we chose

Some choices were not settled by the product rules in [principles.md](principles.md). For each
one we took the most conservative reasonable default (quieter, safer, simpler) and wrote down
the alternative. Most of them can be switched with a one-line change in a data file.

## Engine and levels

| # | Question | Default chosen | Alternative | Where to change |
|---|---|---|---|---|
| 1 | Does "two or more rule breaches" (L3) count borrowed or emergency money? | Yes: any 2 of max-share, max-amount, borrowed, emergency | Only the person's own written rules count | `level_rules.multiple_rule_breaches` in `data/policy/intervention.yaml` |
| 2 | One medium content signal alone (e.g. a guaranteed-return claim) | L1; it reaches L2 with a behavioural trigger or a second medium signal | L2 | add a level rule |
| 3 | Several low content signals together | Never above L1 ("a single low signal never alarms", extended to several) | Two lows → L2 | add a level rule |
| 4 | Recent loss + leverage, or high frequency + leverage | L1 | L2 combination rules | add rules |
| 5 | Where is a decision plan expected? | Derivatives and crypto only (elsewhere it would nudge every ordinary decision) | All product classes | `params.plan_expected_for` |
| 6 | When is the "already paid?" recovery entry shown? | When message signals alone reach L3 | From L2 | `params.recovery_min_content_level` |
| 7 | A model-only high-severity signal at `unclear` certainty | Still counts for L3 (certainty never hides fraud), shown as "Unclear"; it needs a verbatim quote | Exclude `unclear` model-only signals from escalation | `engine/levels.py` |
| 8 | Policy numbers (L1 budget 3 a week, decay streak 5, default cooling-off 15 min, 10/25/50% illustrations) | Proposals | Numbers from a pilot | `params` |

## Stages and routing

| # | Question | Default chosen | Alternative |
|---|---|---|---|
| 9 | A forwarded tip or offer with no note from the person | `consider_action` (the share happens at the moment of deciding) | `evaluate_content`, or ask |
| 10 | `already_acted` together with acting words | Ask (`unknown`) | Recovery first |
| 11 | High-severity content signal while amount or funding are missing | Show the warning at once and ask afterwards | Ask first |
| 12 | Pre-filling recovery answers from the text (paid? how? app?) | Yes, yes/no facts and payment method only; the person can correct them | Always ask |
| 13 | Does a content report show a level? | No: signals with severity and certainty only (a level reads like a verdict) | Show the content-dimension level |

## Facts and production

| # | Question | Default chosen | Alternative |
|---|---|---|---|
| 14 | Production hides unverified facts, which would also hide 1930 and the portals until verified | Hide (the rule as written); the recovery routes have since been verified | Exempt safety-critical recovery routes |
| 15 | Glossary entries cite the SEBI investor website home page | Generic pointer, specific pages marked TODO_VERIFY | Link each term's page |
| 16 | Capital-gains card | Only when the action is selling; hidden in production until verified | Never show tax |
| 17 | Production hides lessons and the Learn list until their text is marked verified | Hide, with a calm empty state; a demo can set `RUKO_SHOW_UNVERIFIED_FACTS=true` and say so | Exempt lessons from the rule |
| 18 | `/docs` (the interactive API page) stays public in production | Kept: it shows the contract and holds nothing secret | Disable it in production |

## Privacy and providers

| # | Question | Default chosen | Alternative |
|---|---|---|---|
| 19 | Screenshots and voice notes reach the OCR / speech provider unredacted | Accepted for the prototype, in memory only, and documented | On-device OCR and speech, sending only text |
| 20 | Gemini free tier quotas | Keep; a fallback model and the pattern-only path cover outages | Paid tier |
| 21 | The rate limiter is in memory, per process | Fine for one instance | A shared store for several instances |
| 22 | Signals quote the person's own words | Yes: a plain substring of the redacted text, at most 140 characters, never logged or spoken, hidden when there is no message text | Show no quotes |

## Guardrails

| # | Question | Default chosen | Alternative |
|---|---|---|---|
| 23 | Shared text that tells an "assistant" to act as an adviser | Refused as `ROLEPLAY_ADVISOR` (over-refusal is the safe side) | Analyse it as content |
| 24 | Deterministic gate coverage on unseen phrasing | The held-out baseline was 6/16 before generalisation; the model's second opinion adds refusals when configured | Require the model classifier in production |
| 25 | "How much should I invest each month for my goal?" | Refused as advice; "how much should I save…" goes to the goal calculator | Route goal-shaped "invest" questions to the calculator |

## Calculators

| # | Question | Default chosen | Alternative |
|---|---|---|---|
| 26 | Example rates (SIP/goal 0%, 6%, 12%; inflation 4%, 6%, 8%; falls 10%, 25%, 50%) | Labelled "example rates for illustration, not expectations"; the person's own rate is added, never replaced | Different sets, or always ask |
| 27 | Model help in the calculate stage | The model may only name the calculator; it never outputs numbers | Let it extract amounts, months and rates as structured fields |
| 28 | Tax calculator | Not built until the rules are verified | Build after verification |
| 29 | Trading-cost calculator | Two hypothetical cost assumptions (₹20 a trade; 0.5% of value), labelled as not any broker's charges; statutory charges unused until verified | Use verified statutory charges |
| 30 | Calculation lines with amounts in words are not read aloud (speech slots accept only number-like values) | Keep the speech rule strict | Allow a words slot for speech |
| 31 | The calculator starts empty | Shows a result only once the required numbers exist | Start with an example |

## Learn

| # | Question | Default chosen | Alternative |
|---|---|---|---|
| 32 | Model-written explanations | Not built: lessons and word explanations are curated templates | A grounded, validated generator as an explicit change of principle |
| 33 | Lesson budget | At most 2 lessons; cards + lessons at most 3, ranked together (safety-critical first); a lesson replaces the card on the same topic | Lessons on top of 3 cards |
| 34 | Listening to a lesson | Reads the plain body by lesson id (no personal numbers) | Read the version with the person's amounts |
| 35 | Lesson wording from SEBI's scam guides | Quotes read from the guides' PDFs and stored with their source in `data/facts/investor_pages.yaml` | Wait for a human check before writing lessons |
| 36 | Lessons with no factual claim (forwarded tips, decision plan, emergency money) | Marked as general guidance from Ruko, not from an official source, and contain no numbers | Cite the SEBI website, which would imply SEBI backs Ruko's habit advice |
| 37 | Which lessons count as read | Only non-critical ones fade; safety-critical lessons always show | Mark every lesson read |
| 38 | Home suggests a lesson | Only when nothing else is pending; "Not now" hides it for the day | Always show it, or never |
| 39 | Tappable words | Once per text, at most 3 per text and 14 per response | Highlight every occurrence |
| 40 | Glossary answers offer related terms | At most 8, same subject first | Show all |

## The app

| # | Question | Default chosen | Alternative | Where |
|---|---|---|---|---|
| 41 | "Intervention style" (quiet / balanced) | A device-only setting that trims the optional question on an L1 nudge; the backend still decides everything else | Send the preference to the backend | `PauseCard`, `config/defaults.ts` |
| 42 | What "skip, use safe defaults" means | An empty profile: Ruko never writes rules for the person or compares with figures it made up | Pre-fill a conservative cooling-off or share limit | `config/defaults.ts` |
| 43 | Attention counts | The phone counts the last seven days of pauses and the rule-following streak and sends them, which switches on the weekly budget and friction decay | Send zeros | `services/profile.ts` |
| 44 | Amount and funding hints | Offered as taps from the message; never filled in automatically | Pre-fill | `data/policy/clarify.yaml` |
| 45 | Pace | Three skipped reflections (L1 or L2) offer the decision directly; L3 is never shortened | A different count, or none | `state/reflection.ts` |
| 46 | When a "wait" comes back | After the person's own cooling-off minutes, else one day; a note on the phone, no push | Always one day | `services/memory.ts` |
| 47 | Late night | 23:00 to 05:00 on the phone's clock, sent as yes/no; never raises a level alone | Let the person set their own night hours | `services/clock.ts` |
| 48 | Service worker | Pages network-first (new releases arrive when online), built files cache-first, the API never cached | Precache everything for a fully offline first launch | `public/sw.js` |
| 49 | Content-Security-Policy | Own files only, with `style-src 'unsafe-inline'` for a few inline style values | A hash-based policy once inline styles are moved to classes | `src/ruko/api/static.py` |
| 50 | Fictional broker demo wording | English only; reason codes become plain statements about the person's own setup | Translate it | `mock-broker/labels.ts` |
| 51 | Pilot control arm ("always prompt") | Delivered by the facilitator as a fixed card; no in-app switch | A pilot-only flag | `docs/pilot_protocol.md` |

## Evaluation

| # | Question | Default chosen |
|---|---|---|
| 52 | The same team wrote the patterns and the evaluation sets | Stated in the report; a truly blind set needs other people's messages |
| 53 | The calculator and lessons split | Written from the design before its first run, so it is a regression check, not a blind set; one wrong label was corrected after the first run and says so in the file |
