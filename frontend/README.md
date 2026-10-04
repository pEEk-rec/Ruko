# Ruko frontend

Mobile-first React + TypeScript (Vite) app against the `/v1` backend. The Figma export in
`design/Ruko — UX/` is the visual reference; the backend decides everything about the decision.
The app connects features and logic only: all visual values live in `src/styles/tokens.css`, and
screens reuse the existing component classes. Status: **phase 2 wired (P3 to P6), not yet reviewed
by the owner**.

## Dry run (two terminals)

```bash
# 1. backend (repo root)
.venv/Scripts/python -m uvicorn ruko.main:app --port 8000

# 2. frontend
cd frontend
npm install          # first time only
npm run dev          # http://localhost:5173  (proxies /v1 to :8000, no CORS change needed)
```

Open http://localhost:5173 in Chrome, press F12 → device toolbar → 390×844 (and 360×740).
First run shows the welcome flow (language, your own rules, how much Ruko speaks, or "Skip, use
safe defaults"). To see it again: DevTools → Application → Local storage → clear `ruko.*`.

### Manual dry-run checklist

Tick each line; "Expect" is what should happen. Items marked (key) need the Sarvam key in `.env`.

| # | Do this | Expect |
|---|---|---|
| 1 | First run: pick हिन्दी | The whole screen switches to Hindi at once; a line says the translation is a draft |
| 2 | Skip (safe defaults) | Home, in the chosen language; the Rules screen shows nothing set |
| 3 | Settings → turn on Large text | Text grows; you stay on Settings; reload keeps it |
| 4 | Share: `Guaranteed 3x return in 7 days. Join our Telegram group, act today!` → `20000`, "My emergency money", "A scheme, app or platform" | 3 questions → L2 pause with a short lesson ("Why promised returns matter"), a Listen button, Learn, Think this through |
| 5 | Tap **Learn why this matters** | Cards and lessons together are at most 3; each lesson has read time, sources, "Not yet checked by a person" |
| 6 | Set My rules (max 10 %, no borrowed money, cooling-off 15) then `Thinking of buying 1 lot of nifty options` → `40000`, borrowed, F&O | L3 pause with a countdown ("A moment to wait"); **Skip the wait** works; Continue is always there |
| 7 | Finish a decision | Journal note saved; after a pause a one-tap "How did that pause feel?" appears (once a week) |
| 8 | Listen on a pause (key) | Ruko's voice reads it. With no key or the backend off: your phone's voice reads it and says so |
| 9 | Compose → **Speak instead** (allow the microphone) (key) | Recording counter (max 30 s) → Stop and send → a result. Deny the microphone: a calm message, typing still works |
| 10 | Home → **Work out a number**: `SIP of 5000 a month for 10 years` | Scenarios side by side, a line chart, "An illustration of arithmetic, not a prediction", a lesson with Listen |
| 11 | Home → **Work out a number**: `I put 50k in options with 5x leverage, what if it drops 25%` | Bar chart of the loss for each fall with a marker at the money put in |
| 12 | Home → **I already paid** → yes → UPI → "refusing to let you withdraw": yes | Steps in order (1930 is a tap-to-call link), tick boxes that survive a reload, a copyable draft; no promise of a refund |
| 13 | Home → **My patterns** (after 3+ journal notes) | The backend's numbers in plain words and "not a score"; offline: "Patterns need a connection" |
| 14 | `Is this message real? Guaranteed 3x return` | Content report (no verdict), safety lessons |
| 15 | `What is an IPO?` / `Should I buy Reliance?` / `good morning` | Glossary / refusal / "What would you like Ruko to do?" |
| 16 | Settings → tap the version line 5 times → **Fictional broker demo** | `/demo/broker`: "Demo – not a real broker"; place an order with leverage and borrowed money: a pause sheet in plain words; "Place order anyway" always works; the outcome is in your journal |
| 17 | Settings → **Download my anonymised summary** | A JSON file of counts only (open it and check: no text, no amounts) |
| 18 | Stop the backend, submit anything | Calm "can't be reached" + Try again; the offline notice appears when the phone is offline |
| 19 | 360 px width with Large text on | No horizontal scroll; every button at least 44 px tall |

Share target in the browser: `http://localhost:5173/?text=Guaranteed%203x%20return` simulates a share.

## Commands

```bash
npm test                # vitest (real backend responses in src/fixtures/)
npm run typecheck       # tsc -p .
npm run build           # type check + production build
npm run check:size      # gzip sizes and the bundle budget (run after build)
# regenerate fixtures from the real backend (repo root):
.venv/Scripts/python frontend/scripts/capture_fixtures.py
```

## Structure

```
src/types/api.ts        mirror of backend models (field names from src/ruko/models/)
src/services/api.ts     fetch + timeout + typed errors for analyze, voice, recover, journal review,
                        speak and order-intent; validate.ts = runtime response checks
src/services/device.ts  profile, journal, evidence ticks in localStorage (device only)
src/services/profile.ts the profile sent with each request + attention counts from the journal
src/services/settings.ts language, text size, intervention style, first-run flag (device only)
src/services/recorder.ts  MediaRecorder with the backend's limits (30 s, 5 MB)
src/services/listen.ts  Ruko's voice via /v1/speak, the phone's voice as the fallback
src/services/summary.ts the anonymised summary (counts only)
src/config/defaults.ts  the one place for first-run defaults (mirrors the backend profile)
src/state/flow.ts       reducer: one screen per backend `kind`; never computes a level
src/hooks/useDecisionFlow.ts  wires reducer, API, voice and the device store
src/components/         presentation; charts/ are plain SVG, loaded lazily
src/screens/            screen composition (ResultScreen = ResultRenderer: one switch on `kind`)
src/mock-broker/        the fictional broker demo (lazy; /demo/broker)
src/pwa/register.ts     service worker registration (production build only)
src/copy/{en,hi,kn}.ts  chrome text; hi and kn must define every key (the compiler checks), all drafts
src/styles/tokens.css   design tokens (replace with exact Figma values; large-text mode lives here too)
public/                 manifest (with share_target), icons, sw.js
```

## Figma → React → backend mapping

| Figma | React | Backend |
|---|---|---|
| Header "ruko · Private by design" | `RukoHeader` | — |
| Home | `HomeScreen` | — |
| Shared message bubble | `SharedContent` | `AnalyzeRequest.input` |
| "Looking at what you shared…" | `ProcessingState` | in-flight `POST /v1/analyze` |
| Headline | `RukoMessage` | `PauseResponse.headline` (and other kinds' headline/title/message) |
| "What I see" rows | `SignalCard` | `signals[]` → `SignalView.reason_text` |
| Likely / Possible pill | `ConfidenceBadge` | `SignalView.certainty_label` |
| "Your context" | `PersonalContextCard` | `rules_text[]`, `numbers_text[]` |
| Small nudge / closer look / deliberate pause | `PauseCard` (one component) | `PauseResponse.level` L0–L3 |
| "Is this decision consistent…?" | question line in `PauseCard` | `PauseResponse.question` |
| "Why this matters" / Learn | `LearnScreen`, `LearnCard`, `LessonCard` | `cards[]`, `lessons[]` |
| "Continue anyway" | `ActionButton` | `override_label` (`decision.override_allowed` is always true) |
| Clarification | `ClarifyScreen` / `ClarificationChoice` | `ClarifyResponse.questions[]`, answers resent in `answers` |
| Reflection choices + free text | `ReflectionChoice` | **none** (device only) |
| Decision recorded / journal | `JournalSavedScreen`, `JournalSummary` | `JournalEntry` shape (models/journal.py), stored on device |
| (not in Figma) waiting period | `CoolingOffTimer` | `decision.cooling_off_minutes` (L3) |
| (not in Figma) calculation | `CalculationCard` + `charts/` | `CalculationResponse` (scenarios, series) |
| (not in Figma) recovery | `RecoverFormScreen`, `RecoveryGuideView` | `POST /v1/recover`, `RecoveryGuide` |
| (not in Figma) my patterns | `MirrorScreen` | `POST /v1/journal/review` |
| (not in Figma) welcome, settings | `OnboardingScreen`, `SettingsScreen` | `UserProfile` (device) |
| (not in Figma) fictional broker | `mock-broker/BrokerApp` | `POST /v1/order-intent` |
| content report, glossary, refusal, errors | `ResultScreen` views, `ErrorScreen` | `content_report`, `glossary`, `refusal`, error envelope |

## Contract notes (backend unchanged by the frontend)

1. **Figma screen 2 shows the user typing "Should I do this?"** The backend input guardrail refuses
   advice requests, so a free-text note like that returns a refusal. There is no note box; intent
   comes from the stage question / "Think through a decision" (`answers.stage`).
2. **Reflection has no backend contract.** The choices are frontend copy, stored on the device only.
3. Fixed in phase 2: `severity` in pause signals, separate `certainty_label` / `reason_text`,
   `PauseResponse.event`, `lessons[]`, `/v1/speak` by `lesson_id`.
4. **"Intervention style" (quiet / balanced)** has no backend field. It is a device setting that only
   trims the optional question on a small nudge; the backend still decides what is shown.
5. **Device-only note fields** (`cooling_off`, `feeling`, `origin`, `input_kind`) are in a journal
   record's `notes`, never in its `entry`, so `/v1/journal/review` (which rejects unknown fields)
   only receives the backend's own `JournalEntry` fields.
6. **Screenshots can be shared into the app from the share sheet.** The share target is a POST
   (`multipart/form-data`: title, text, url and a `media` image). The service worker turns text into
   `/?text=…` and holds an image in a short-lived inbox until the app reads and deletes it
   (`src/share/readSharedContent.ts`, `public/sw.js`).
7. The recovery form replaces the earlier "stage = already acted" shortcut. The pause's and the
   content report's "Already paid?" link now opens the form.

## Offline and bundle budget

- `sw.js` caches the app shell. Page loads are network-first (a new release arrives as soon as the
  phone is online); built files are served from the cache; `/v1/*` and `/health` are never cached.
  Rules, journal and the checklist work offline; analysis and My patterns need a connection and say so.
- Budget (checked by `npm run check:size`): entry JS ≤ 100 KB gzip, CSS ≤ 10 KB gzip; charts and the
  broker demo are lazy chunks. Last build: entry JS 75.3 KB, CSS 2.8 KB, charts 1.3 KB, broker 2.1 KB.
  No web fonts (system fonts only).

## Device test instructions (user device test pending)

**1. Start Ruko on the laptop (one terminal, one port)**

```bash
cd frontend
npm run build
cd ..
# PowerShell:
$env:RUKO_STATIC_DIR="frontend/dist"; .venv\Scripts\python -m uvicorn ruko.main:app --port 8000
# Git Bash:
RUKO_STATIC_DIR=frontend/dist .venv/Scripts/python -m uvicorn ruko.main:app --port 8000
```
Use the built app, not `npm run dev`: install and the service worker only exist in the build.
With your `.env` Gemini key, the LLM is used. Development mode is the default, so the lessons are visible. Check on the laptop that http://localhost:8000 opens Ruko.

**2. Get the app onto the phone**

**Option A: USB cable (recommended).** The phone sees it as localhost, so install, share and microphone all work, and the address never changes.
- Phone: Settings → About phone → tap Build number 7 times. Then Developer options → turn on USB debugging.
- Connect the cable and accept "Allow USB debugging" on the phone.
- Laptop Chrome: open `chrome://inspect/#devices` → Port forwarding… → add 8000 → localhost:8000 → tick Enable port forwarding → Done.
- Phone Chrome: open http://localhost:8000. Keep the cable plugged in while testing.

**Option B: tunnel (no cable, like the spike).**
- In a new terminal run: `cloudflared tunnel --url http://localhost:8000`
- Open the printed `https://….trycloudflare.com` on the phone. The URL changes every run, so you'd reinstall each time.

**3. Install the real app**

- Remove the old spike: long-press the "Ruko test" icon → Uninstall.
- In phone Chrome, on the Ruko page: menu ⋮ → Install app (or Add to Home screen).
- Open Ruko from its new icon. It should open full screen, without the address bar.
- If an old version ever shows: Chrome → Settings → Site settings → All sites → localhost → Clear & reset, then reopen.

**4. What to try and observe**

| # | Do | Expect |
|---|---|---|
| 1 | First run: pick a language, set your rules | Home with a Learn tile. About a second later, an "A lesson for you" card appears. |
| 2 | Tap Learn | "0 of 15 read", "Next for you", four headings, and a row of word chips. |
| 3 | Tap a word chip (for example Margin) | A dark pop-up opens with a short explanation. Close it with the button or by tapping elsewhere. |
| 4 | Open a lesson and tap a dotted word | The pop-up opens above the word; near the top of the screen it opens below. Read next goes to the next lesson. |
| 5 | Go back to the list | The lesson you read shows a ✓ and the count goes up. |
| 6 | In WhatsApp or Telegram: long-press a message → Share → Ruko | Ruko opens and checks it straight away. |
| 6b | In WhatsApp or Telegram: open a photo or screenshot → Share → Ruko | Ruko opens and reads the picture (needs the Gemini key). If Ruko is missing from the photo share list, uninstall and reinstall once. |
| 7 | Share *Guaranteed 3x return in 7 days. Join our Telegram group, act today!*, answer ₹20000 / emergency money / scheme | A pause with signals, your own rupee numbers, and tappable words. *Learn why* shows the lesson. |
| 8 | Share *What is an IPO?* | An explanation with tappable words and a "Worth knowing" lesson card. |
| 9 | Work out a number → SIP 5000, 120 months | Numbers update live, with tappable words like "SIP" and a lesson card. |
| 10 | Share something → Speak instead | The microphone permission is requested and the voice note is checked. |
| 11 | Settings → Hindi, then Kannada | Learn, lessons and pop-ups switch language. Note any odd wording. |
| 12 | Airplane mode, then reopen | Rules and Journal still open, and an offline notice appears. |
| 13 | (Late night) Use it after 11 pm | "It is late at night where you are…" appears among the signals when a message has a medium-level signal. Learn puts *A plan you write before you act* first. |

## Pending

- Owner: review this mapping; send exact Figma tokens (Copy as code → CSS) for `tokens.css`.
- Native-speaker review of every Hindi and Kannada string (all are drafts: `src/copy/index.ts` lists
  none as verified).
- Real-device test (above). Nothing here has been run on a phone.
- Not committed (git needs your approval); proposed commits are in `STATUS.md`.
