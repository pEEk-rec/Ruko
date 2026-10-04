# BUILD_PLAN_2.md: Ruko phase 2, integration and new capabilities

Read `CLAUDE.md`, this file, `STATUS.md`, `docs/decisions.md`, `docs/open_questions.md` and `frontend/README.md` before starting. Same rules as phase 1: autonomous mode with the hard and soft gates in `CLAUDE.md` section 4, no git while the user is away (proposed commits go in `STATUS.md`), no AI attribution anywhere.

Start a **fresh session after every two stages**: re-read the files above and continue from `STATUS.md`.

---

## A. Where we are (verified 4 Oct 2026)

- Backend: stages 0 to 13 done; 892 offline tests pass; ruff clean; guardrail suite 100%; 16 golden scenarios. Not deployed.
- Frontend: React + TypeScript (Vite) baseline wired to `POST /v1/analyze` only; 30 tests pass; English chrome text only; no service worker.
- **Not yet built or not wired:** voice in/out in the UI, `/v1/recover` form, `/v1/journal/review` mirror, Hindi/Kannada UI text and a language switcher, the mock broker, calculators, the consequence simulator as a standalone tool, decision-specific Learn beyond the 10 cards and 8 glossary terms, impact instrumentation.
- Probe result: "What will my SIP of 5000 a month look like?" and "What happens to 40000 if this falls 25%?" currently return a generic clarify. There is no calculation path.

## B. Phase 2 decisions (add these to `CLAUDE.md` as section 1.5 in Stage P0)

1. **New decision stage `calculate`.** "What will my SIP look like?", "what if this falls 25%?", "how much should I save for my goal?" route to a calculation tool, not the pause engine and not a refusal. A calculation question is not an advice request unless it asks which product or what to buy.
2. **Tool selection may use the LLM; the numbers never do.** Deterministic patterns pick the tool first; the LLM may fill an unknown tool choice and extract parameters (amount, months, rate) as structured fields. Every number in the answer comes from tested pure functions. Missing parameters become clarify questions.
3. **No predictions.** Calculators are illustrations of arithmetic under assumptions the **user** supplies or that are clearly labelled. Ruko never suggests an expected return, never says what a product "will" earn, and always shows at least two scenarios side by side. Each result carries `assumptions[]` and `is_illustration: true`.
4. **Dynamic Learn stays grounded and template-based in v1.** "Dynamic" means Ruko *selects and orders* short, verified micro-lessons for this decision, fills them with the user's own numbers, and offers read or listen (TTS). The LLM does not write lesson text. Every lesson is in a data file with sources and `verified_by_human`, like the cards. (If the user later wants LLM-written explanations, that is a separate, explicit change to `CLAUDE.md` principle 6, with a grounding and validator design. Do not build it now; record it in `open_questions.md`.)
5. **The UI renders structured results; it never computes levels or numbers.** React owns components; the backend returns typed `kind`s and card types.

---

## C. Stages

Each stage: Goal, Build, Rules, Tests, Done when. Update `STATUS.md` and `docs/decisions.md` after each.

---

### Stage P0: Housekeeping and contract fixes

**Goal:** a clean, accurate starting point and the backend fixes the frontend already found.

**Build**
- Update `STATUS.md` to reflect reality (what is committed vs not; phase 2 starting). Add section 1.5 to `CLAUDE.md` from section B above.
- Fix the frontend-found contract mismatches (`frontend/README.md`, "Contract mismatches"):
  - fill `SignalView.severity` in pause responses
  - add a prefix-free signal text field (keep the existing field for compatibility) so the certainty badge is not duplicated in hi/kn
  - include a minimal `event` summary in `PauseResponse` (stage, product class, source type, action; no message text) so the journal doesn't depend on clarify state
- Update `frontend/src/types/api.ts`, `validate.ts` and fixtures to match; regenerate fixtures from the real backend.

**Tests:** backend model and golden tests updated; frontend tests updated.

**Done when:** both suites pass; `docs/api_contract.md` updated.

**[GIT CHECKPOINT]** `Fix pause response fields for the frontend`

---

### Stage P1: Calculation tools (backend)

**Goal:** answer "what will this look like" questions with deterministic illustrations.

**Build**
- `src/ruko/tools/` with pure functions, integer rupees, documented formulas, no I/O:
  1. `sip_illustration(monthly, months, annual_rates[])`: future value per rate, total invested; returns a small yearly series for charting
  2. `inflation_purchasing_power(amount, years, inflation_rates[])`: what today's amount buys later; and "real" value of a nominal amount
  3. `goal_contribution(goal_amount, months, annual_rates[], already_saved)`: monthly amount needed per rate
  4. `consequence(amount, drops_pct[], leverage=1)`: rupee outcome for each illustrative fall (reuse `engine/exposure.py`; never a probability); with leverage, show that losses can exceed the amount put in, using the verified fact card
  5. `cost_illustration(trade_value, trades_per_month, cost_params)`: costs over a period; cost parameters come from a sourced data file (`data/facts/charges.yaml`, `verified_by_human: false`, TODO_VERIFY where unsourced); hidden in production until verified
  6. `tax_illustration`: **build last and keep disabled** (`enabled: false` in `data/policy/tools.yaml`) unless the user verifies the rules; record in `open_questions.md`
- Rates: the user supplies them, or the tool uses a labelled set from `data/policy/calculators.yaml` described as "example rates for illustration, not expectations" (user to review). Never a single rate.
- Stage `calculate`: patterns in `data/stages/{en,hi,kn}.yaml`; tool choice patterns; LLM may fill tool and parameters via the existing extraction path with a new schema version; parameters validated with Pydantic and sane bounds (amount, months up to 600, rates within a documented range).
- Response `kind: "calculation"`: tool id, inputs echoed, `assumptions[]`, `scenarios[]` (label + numbers + optional series), `headline` and `explanation` from templates (en/hi/kn) with numbers in words, `is_illustration: true`.
- Guardrails: output validator rules for `response_type: calculation`: forbid "you will get / will earn / expected / guaranteed" assertions; allow "at an assumed X% a year, the arithmetic gives…". Gate still refuses "which fund gives the best return" (advice).
- Tool allow-list updated.

**Tests:** hand-computed values per function (including edge cases: 0 months, 0 rate, large values); property tests (more months never reduces SIP value at a positive rate; a larger fall never gives a better outcome); routing tests in three languages; guardrail tests for calculation phrasing (prediction-style requests framed as "what will Nifty be next year" still refused); golden scenarios for each tool.

**Done when:** tests pass; guardrail suite 100%; `/docs` shows the calculation kind.

**[GIT CHECKPOINT]** `Add calculation tools and calculate stage`

---

### Stage P2: Decision-specific Learn (backend)

**Goal:** short, verified explanations chosen for this decision, readable or listenable.

**Build**
- `data/learn/lessons.yaml`: micro-lessons (about 60 to 120 words each), en/hi/kn, each with id, triggers (product class, action, reason codes, stage), sources, `as_of`, `verified_by_human`, estimated read time, optional slots for the user's numbers. Starter set mapped to the user's examples:
  - leverage: what it actually does (F&O tip)
  - what an IPO offers you and what it doesn't (IPO message)
  - why guaranteed-return claims are a red flag (guaranteed-return message)
  - charges and tax exist when selling (selling; tax lesson gated like the tax card)
  - how SIP contributions add up (SIP question; links to the SIP tool)
  - check registration yourself (authority claim)
  - why you never pay a person to "release" profits (withdrawal fee)
- `learn/select.py`: deterministic selection, max 2 lessons per decision (on top of the existing max-3 cards rule, total explanation items capped at 3), seen-lesson fading, safety-critical override.
- Attach selected lessons to `PauseResponse`, `ContentReportResponse` and `CalculationResponse` as `lessons[]`; `/v1/speak` accepts a lesson id to read it aloud.
- Expand the glossary only where lessons need a term.

**Rules:** no lesson recommends a product or compares products; all pass the output validator in all locales; unverified lessons hidden in production.

**Tests:** trigger and cap tests; fading; validator on all lessons; speak-by-id.

**Done when:** tests pass.

**[GIT CHECKPOINT]** `Add decision-specific lessons`

---

### Stage P3: Frontend integration of existing endpoints

**Goal:** every backend capability that exists is usable from the app.

**Build**
- **Voice in:** record (MediaRecorder), size/duration limits matching the backend, send to `/v1/analyze/voice`; clear permission and failure states; text path always available.
- **Voice out:** "Listen" on pause, Learn, calculation and recovery screens via `/v1/speak`; falls back to the browser's speech synthesis if the provider is unavailable, and says so.
- **Recovery form:** the `/v1/recover` questions (paid? how? app installed? fee demanded?), tap-to-call, copyable draft complaint, evidence checklist with tick boxes stored on device.
- **Mirror:** "My patterns" screen calling `/v1/journal/review` with the device journal; render the impact metrics in plain words; nothing leaves the device except the journal entries in that request.
- **Language:** complete `copy.ts` for hi and kn (mark every string `draft` for native review), a language switcher on first run and in settings, locale sent with every request.
- **Onboarding rules:** first-run flow for personal rules, protected goals, emergency buffer, language and intervention preferences (quiet / balanced), with "skip, use safe defaults". Defaults defined in one data file; mirror the backend profile model exactly.
- **Accessibility:** large-text mode, minimum 44px tap targets, numbers shown with Indian grouping and in words where the backend provides them, works at 360px width.

**Tests:** component tests for each new screen; flow tests for voice failure, recovery, mirror; type check and build pass.

**Done when:** all tests pass; a manual dry-run checklist added to `frontend/README.md`.

**[GIT CHECKPOINT]** `Wire voice, recovery, mirror and languages in the app`

---

### Stage P4: Dynamic result cards in the frontend

**Goal:** the UI renders the right component for each structured result instead of a chat transcript.

**Build** components mapped one-to-one to backend structures:
- warning / signal card, personal-rule card, Learn card (read + listen), **calculation card** (scenario table plus a simple line or bar chart of the series; label "illustration, not a prediction"), **consequence chart** (bars for each illustrative fall), clarification prompt, **cooling-off timer** (for L3 with the user's own cooling-off minutes; skippable, skip recorded), recovery checklist, journal card.
- A single `ResultRenderer` that switches on `kind` and card type. No component computes a level or a number.
- Charts: a small dependency only if needed (ask in `open_questions.md`; prefer plain SVG).

**Tests:** renderer test per `kind`; snapshot or role-based tests for each card; timer skip recorded in the journal entry.

**Done when:** tests pass; every `kind` from `/v1/analyze` renders.

**[GIT CHECKPOINT]** `Add result cards, charts and cooling-off timer`

---

### Stage P5: Mock broker demo surface

**Goal:** show the embeddable story: a fictional broker calls Ruko before an order.

**Build**
- `frontend/src/mock-broker/`: a clearly fictional broker order screen (invented name, a "Demo – not a real broker" banner, no real instrument names; use placeholders like "Stock A", "Index option B").
- On "Place order", it calls `POST /v1/order-intent` with product class, amount band, funding flag, leverage flag, plan-match flag and the device profile; no instrument identity, no user ID.
- Renders the returned level and reason codes as the broker would (inline pause sheet), with "Continue" always available; logs the outcome to the device journal.
- Route `/demo/broker`; link from a hidden demo menu, not the main home.

**Rules:** no real broker names, logos or look-alike designs (guardrail and impersonation rules).

**Tests:** request contains no instrument identity; L0 passes silently; L2/L3 show the sheet; continue always works.

**Done when:** tests pass.

**[GIT CHECKPOINT]** `Add fictional broker demo using order intent`

---

### Stage P6: PWA and share target in the real app

**Goal:** Ruko installs on Android and appears in the share sheet.

**Build**
- Move the proven parts of `spike/share_target/` into `frontend/`: manifest with `share_target`, a service worker (offline shell for rules, journal and mirror; analysis needs the network and says so), icons.
- Low-bandwidth: bundle size budget (record it), lazy-load charts and the mock broker, no web fonts beyond one family.
- Device-test instructions for the user in `frontend/README.md` (install, share from Telegram/WhatsApp, screenshot share, voice permission). Mark "user device test pending".

**Tests:** manifest validation test; service-worker registration test; build size reported.

**Done when:** build passes; size within budget or the excess explained.

**[GIT CHECKPOINT]** `Make the app installable with share target`

---

### Stage P7: Impact instrumentation and evaluation update

**Goal:** evidence for the jury, measured on the device and in the eval.

**Build**
- Device journal fields for: pause completed, reconsidered (changed amount / delayed / set a plan / cancelled), override with reason, could state why, annoyance rating (optional 1-tap after a pause, at most once a week), recovery checklist completion.
- Export: "Download my anonymised summary" (counts only, no message text) for the user's pilot.
- `docs/pilot_protocol.md`: a short scenario-based pilot plan (always-prompt vs adaptive, 10 to 20 volunteers, consent text, what is recorded, no personal data).
- Eval: add calculation routing and lesson selection to `eval/run_eval.py`; keep the held-out split honest.

**Tests:** journal schema tests; export contains no free text; eval runs.

**Done when:** tests pass; report regenerated.

**[GIT CHECKPOINT]** `Add impact measures and pilot protocol`

---

### Stage P8: Full-stack hardening and demo readiness

**Goal:** one command runs everything; a judge's first click works.

**Build**
- Serve the built frontend from the backend container (or a documented two-service setup); single Dockerfile path; production config hides unverified facts.
- End-to-end smoke script (Playwright with the preinstalled browser if available, else a scripted HTTP check) covering: share → pause → learn → decide → journal; calculation; recovery; refusal; mock broker; language switch.
- `docs/demo_script.md`: the 3 to 5 minute demo path with exact inputs, including one quiet (L0) case, one pause, one calculation, one recovery, one refusal, and the mock broker.
- `STATUS.md`: the user's pre-demo checklist (deploy host choice, keys and quotas, fact verification, native-speaker review, device test).

**Done when:** smoke test passes locally; deployment still waits for the user.

**[GIT CHECKPOINT]** `Serve app from backend and add demo script`

---

## D. Phase 2 completion checklist

- [ ] `calculate` stage routes all calculator questions; no prediction language anywhere
- [ ] Every number from deterministic, tested functions; every calculation shows assumptions and two or more scenarios
- [ ] Lessons decision-specific, capped, verified-or-hidden, listenable
- [ ] Voice in and out, recovery form, mirror, hi/kn UI, onboarding rules all working in the app
- [ ] Every `kind` renders as a structured card; cooling-off timer works and is skippable
- [ ] Mock broker is clearly fictional and sends no instrument identity
- [ ] Installable PWA with share target; device test pending with the user
- [ ] Impact measures recorded on device; pilot protocol written
- [ ] Backend and frontend test suites, lint, type check and build all pass; guardrail suite 100%
- [ ] No AI attribution anywhere
