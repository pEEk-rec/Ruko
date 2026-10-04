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

## Phase 2

| # | Question | Default chosen | Alternative |
|---|---|---|---|
| 25 | LLM-written explanations in Learn | Not built: lessons are curated templates (CLAUDE.md 1.5.4, principle 6) | Explicit change to principle 6 with a grounding and validator design |
| 26 | Example rates for calculators (SIP/goal 0%, 6%, 12%; inflation 4%, 6%, 8%; falls 10%, 25%, 50%) | Labelled "example rates for illustration, not expectations"; the user's own rate is added, never replaced (`data/policy/calculators.yaml`, draft) | Different sets, or no defaults (always ask) |
| 27 | LLM help in the calculate stage | The LLM may only name the calculator; it never outputs numbers (keeps extraction rule 4) | Let the LLM extract amounts/months/rates as structured fields (CLAUDE.md 1.5.2 allows it) |
| 28 | "How much should I invest each month for my goal?" | Still refused as advice (existing gate pattern "how much should I invest"); "how much should I save…" goes to the goal calculator | Route goal-shaped "invest" questions to the calculator too |
| 29 | Tax calculator | Not built; `tax: enabled: false` until the owner verifies the rules | Build after verification |
| 30 | Trading-cost calculator | Uses two hypothetical cost assumptions (₹20 per trade; 0.5% of value), labelled as not any broker's charges; statutory charges in `data/facts/charges.yaml` are all TODO_VERIFY and unused | Use verified statutory charges once filled in |
| 31 | Calculation explanations with amounts in words are not read aloud by `/v1/speak` (its slots accept only number-like values); headline, scenario lines and assumptions are | Keep the speech slot rule strict | Allow a words slot for speech |
| 32 | Lesson budget: lessons share the cap of 3 explanation items with cards | Max 2 lessons; cards + lessons at most 3; ranked together (safety-critical first, then priority, a lesson before a card of equal priority); a lesson replaces the card about the same topic; lessons show from L2 like cards (content reports and calculations from L0, critical only for reports) | Lessons on top of 3 cards (up to 5 items), or lessons at L1 | `data/learn/lessons.yaml` (`max_lessons`, `max_explanation_items`, `pause_min_level`) |
| 33 | `/v1/speak` for a lesson reads the plain body (no user numbers) | Keeps the speech slot rule strict (number-like values only) and works by lesson id alone | Read the amount version via slots | `learn/select.py` `speak_refs_for_lesson` |
| 34 | Lesson wording on SEBI's scam guides | The two guide pages hold their text in a PDF/image; quotes were read from those PDFs on 2026-10-04 and stored in `data/facts/investor_pages.yaml` with `quote_source_url`; all `verified_by_human: false` | Wait for the owner to confirm before writing the lessons | `data/facts/investor_pages.yaml` |
| 35 | Glossary expansion for lessons (BUILD_PLAN_2 P2) | Not needed: the IPO lesson explains ASBA in its own text, so no new glossary term was added | Add an `asba` glossary term | `data/glossary/catalog.yaml` |
| 36 | "Intervention style" (quiet / balanced) in the app | A device-only setting that trims the optional reflection question on an L1 nudge; the backend has no such field and still decides everything else | Send the preference to the backend (for example as a lower attention budget), or add an engine setting | `PauseCard` (`quiet`), `config/defaults.ts` |
| 37 | What "skip, use safe defaults" means | An empty profile: no rules, no amounts, no bands. Ruko never writes rules for the user or compares with figures it made up | Pre-fill a conservative cooling-off or share limit | `frontend/src/config/defaults.ts` |
| 38 | Screenshots shared from the Android share sheet | Not supported: the share target is GET (title, text, url). The user adds a screenshot inside the app | A POST `multipart/form-data` share target plus a service-worker handler that stores the file for the page | `public/manifest.webmanifest`, `public/sw.js` |
| 39 | Attention counts (`profile.attention`) | The device counts the last seven days of L1/L2/L3 and the rules-followed streak from its journal and sends them with each request, which switches on the backend's weekly attention budget and friction decay | Send zeros (budget never applies) | `frontend/src/services/profile.ts` |
| 40 | Pilot control arm ("always prompt") | Delivered by the facilitator as a fixed card; there is no in-app switch | Build a pilot-only flag that makes every decision show the L2 pause | `docs/pilot_protocol.md` |
| 41 | Fictional broker demo wording | English only. Reason codes become plain statements about the user's own setup; the demo journals both "place anyway" and "cancel" | Translate the demo, or show raw codes like a bare API client | `frontend/src/mock-broker/labels.ts` |
| 42 | Which lessons count as seen | Only non-critical lessons are marked seen when a decision is finished (so they fade); safety-critical ones always show | Mark every lesson seen | `useDecisionFlow.finish` |
| 43 | Service worker strategy | Pages network-first (new releases arrive when online), built files cache-first with background refresh, API never cached | Precache a build manifest for a fully offline first launch | `frontend/public/sw.js` |
| 44 | Content-Security-Policy | Set on the app page by the backend (own files only, `style-src 'unsafe-inline'` for a few inline style values); checked by a headless browser in the smoke test; not set on `/docs` (Swagger loads from a CDN) | A hash-based CSP without `unsafe-inline`, once the inline styles are moved to classes | `src/ruko/api/static.py` |
| 45 | A production demo hides unverified facts; after the owner's check, only the lessons, the tax card and `sebi_investor_website` pointers are still hidden | Hide (the rule). The deploy guide offers verify-first, or `RUKO_SHOW_UNVERIFIED_FACTS=true` for a stated, demo-only run | Exempt lessons from the rule | `docs/deploy_cloud_run.md` |
| 46 | `/docs` stays public in production | Kept (it is how a judge sees the contract); nothing in it is secret | Disable docs when `RUKO_ENVIRONMENT=prod` | `src/ruko/main.py` |
| 47 | The phase 2 eval split | Written from the design before its first run, by the same author as the patterns, so a regression check not a blind set. One label (a lesson count that forgot the shared cap of 3) was corrected after the first run and says so in the file; the three real misses were fixed in the patterns | Have someone else write the items | `eval/datasets/phase2.yaml` |
| 48 | Quote echo (A to F, E) | Signals show the person's own matched words (plain substring, redacted, 140 chars, `quote` field only; hidden without message text). Reverses the Stage 2 no-echo rule at the owner's request | Show no quotes | `understanding/quotes.py` |
| 49 | Amount and funding hints | Offered as a tap from numbers in the message; never filled in automatically | Pre-fill | `data/policy/clarify.yaml` |
| 50 | Pace rule | Three skipped reflections (L1 or L2 only) offer the decision directly; L3 never shortened | Different count or none | `state/reflection.ts` |
| 51 | Wait due time | The person's cooling-off minutes, else one day; a note on the device, no push | Fixed one day | `services/memory.ts` |
| 52 | Home nudges | Suggestions only when nothing is pending; "Not now" is remembered | Always show | `state/home.ts` |
| 53 | Calculator starts empty | Shows a result only when required numbers exist; no example numbers | Start with an example | `screens/CalculatorScreen.tsx` |
| 54 | Lessons with no factual claim (`forwarded_tips`, `decision_plan`, `emergency_money`) cite no source | Marked `own_guidance`, shown with "General guidance from Ruko, not from an official source", no numbers (tested) | Cite the SEBI investor website for each, which would imply SEBI backs Ruko's habit advice |
| 55 | Late night comes from the device clock (23:00 to before 05:00 local), sent as a yes/no | `LATE_NIGHT_DECISION`, category `timing`, never raises a level alone | Drop it; or let the person set their own night hours |
| 56 | Home suggests a lesson only when nothing else is pending, after an 800 ms delay, "Not now" hides it for the day | Quiet, one card, no wasted request if the person leaves Home at once | Always show it; or never suggest on Home |
| 57 | A word is tappable once per text (once per lesson body), at most 3 per text, 14 per response | Reading aid, not a field of links | Highlight every occurrence |
| 58 | Glossary pop-up briefs are written in three languages by the builder and marked draft | Review sheet exported; none shown as verified | Hide the pop-ups until verified |
| 59 | In production the Learn list is empty until lesson text is marked `verified_by_human` | Calm empty message; the demo can use `RUKO_SHOW_UNVERIFIED_FACTS=true` and say so | Mark lessons verified after a human reads them |
| 60 | Glossary answers offer at most 8 related terms, same-subject first | Fewer chips | Show all 20 |
