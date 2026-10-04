# Ruko frontend (baseline)

Mobile-first React + TypeScript (Vite) app against the existing `/v1` backend. The Figma export
in `design/Ruko — UX/` is the visual reference; the backend decides everything about the decision.
Status: **baseline, not reviewed**. Backend is unchanged.

## Dry run (two terminals)

```bash
# 1. backend (repo root)
.venv/Scripts/python -m uvicorn ruko.main:app --port 8000

# 2. frontend
cd frontend
npm install          # first time only
npm run dev          # http://localhost:5173  (proxies /v1 to :8000, no CORS change needed)
```

Open http://localhost:5173 in Chrome, press F12 → device toolbar → 390×844. Try:

| Paste this | Expect |
|---|---|
| `Guaranteed 3x return in 7 days. Join our Telegram group, act today!` → amount `20000`, "My emergency money", "A scheme, app or platform" | 3 questions → L2 pause → Think this through → decide → journal |
| `Join now, only today! offer ends soon. Thinking of joining` → `3000`, savings, company shares | L1 nudge |
| Set **My rules** (expenses 25k–50k, savings 1–3 lakh, max 10%, no borrowed) then `Thinking of buying 1 lot of nifty options` → `40000`, borrowed, F&O | L3 pause |
| `Is this message real? Guaranteed 3x return` | content report (no verdict) |
| `What is an IPO?` | glossary |
| `I already paid 5000 by UPI and now they want a fee to withdraw` | recovery guide (1930 tap-to-call, draft complaint) |
| `Should I buy Reliance?` | refusal |
| `good morning` | "What would you like Ruko to do?" |
| Stop the backend, submit anything | calm "can't be reached" + Try again |

Share target: `http://localhost:5173/?text=Guaranteed%203x%20return` simulates a share.

Tests: `npm test` (30 tests, real backend responses in `src/fixtures/`), `npm run typecheck`, `npm run build`.

## Structure

```
src/types/api.ts        mirror of backend models (field names from src/ruko/models/)
src/services/api.ts     fetch + timeout + typed errors; validate.ts = runtime response checks
src/services/device.ts  profile + journal in localStorage (device only)
src/state/flow.ts       reducer: one screen per backend `kind`; never computes a level
src/hooks/useDecisionFlow.ts  wires reducer ↔ API ↔ device store
src/components/         presentation (below)
src/screens/            screen composition
src/share/              share-target boundary (isolated from the flow)
src/copy.ts             frontend chrome text (en; hi/kn entries to add)
src/styles/tokens.css   design tokens (eyeballed from the PNG; replace with exact Figma values)
```

## Figma → React → backend mapping

| Figma | React | Backend |
|---|---|---|
| Header "ruko · Private by design" | `RukoHeader` | — |
| Home | `HomeScreen` | — |
| Shared message bubble | `SharedContent` | `AnalyzeRequest.input` |
| "Looking at what you shared…" | `ProcessingState` | in-flight `POST /v1/analyze` |
| Headline | `RukoMessage` | `PauseResponse.headline` (and other kinds' headline/title/message) |
| "What I see" rows | `SignalCard` | `signals[]` → `SignalView.text` |
| Likely / Possible pill | `ConfidenceBadge` | `SignalView.certainty` |
| "Your context" | `PersonalContextCard` | `rules_text[]`, `numbers_text[]` |
| Small nudge / closer look / deliberate pause | `PauseCard` (one component) | `PauseResponse.level` L0–L3 |
| "Is this decision consistent…?" | question line in `PauseCard` | `PauseResponse.question` |
| "Why this matters" / Learn | `LearnScreen` + `LearnCard` | `cards[]` (`ExplanationCard`) |
| "Continue anyway" | `ActionButton` | `override_label` (`decision.override_allowed` is always true) |
| Clarification | `ClarifyScreen` / `ClarificationChoice` | `ClarifyResponse.questions[]`, answers resent in `answers`, skip → `answers.skipped_fields` |
| Reflection choices + free text | `ReflectionChoice` | **none** (device only) |
| Decision recorded / journal | `JournalSavedScreen`, `JournalSummary` | `JournalEntry` shape (models/journal.py), stored on device |
| (not in Figma) content report, glossary, recovery, refusal, error | `ResultScreen` views, `ErrorScreen` | `content_report`, `glossary`, `recovery`, `refusal`, error envelope |

## Contract mismatches found (backend NOT changed — owner decision)

1. **Figma screen 2 shows the user typing "Should I do this?"** The backend input guardrail refuses
   advice requests, so a free-text note like that returns a refusal. The baseline has no note box;
   intent comes from the stage question / "Think through a decision" (`answers.stage`).
2. **Reflection has no backend contract.** Figma's "What makes you want to do this?" choices are
   frontend copy, stored on the device only. Backend `question` is shown on the pause screen.
3. **`signals[].severity` is `null` in pause responses** (it is set in `content_report` and in
   `decision.reasons[]`). Contract says signals carry severity. Frontend doesn't need it yet.
   Minimal fix: fill `SignalView.severity` in the pause renderer.
4. **Signal text already starts with "Likely: "**, which duplicates the badge. Frontend strips only
   the exact English prefix; for hi/kn it would show twice. Minimal fix: a prefix-free text field.
5. **`PauseResponse` has no `event`**, so the journal's `product_class` / `source_type` come from
   the user's answers or the last clarify `event`, else `unknown`.
6. **"Decision" screen (go ahead / wait / change amount / not do it)** is not in Figma; added
   because the journal needs `JournalEntry.action`.
7. No Figma for content report, glossary, recovery, refusal or errors: built plainly in the same style.

## Pending

- Owner: review this mapping and the mismatches above; send exact Figma tokens (Copy as code → CSS).
- Real-device check at 390×844 and on Android (install PWA, share from WhatsApp/Telegram;
  a service worker is not added yet, so Chrome may not offer install).
- Voice input (`/v1/analyze/voice`) and speak (`/v1/speak`) not wired.
- `/v1/recover` question form not built (recovery uses `answers.stage = already_acted`).
- `/v1/journal/review` (impact metrics) not wired; journal list is local only.
- Hindi/Kannada chrome text (`copy.ts`) and a language switcher.
- Not committed (git needs your approval). Proposed: `Add baseline mobile frontend` — `frontend/`
  (excluding `node_modules/`, `dist/`), and `design/` if you want the exports versioned.
