# Ruko app (frontend)

A mobile-first React + TypeScript PWA (Vite) on top of the `/v1` backend.

**The app shows what the backend decided; it never decides anything itself.** It has no level,
number or verdict logic. Each response `kind` (pause, content report, calculation, recovery,
glossary, refusal, clarify) has its own component. The person's profile, rules, plans and
journal live only in the browser's storage on their phone.

## Run it

```bash
# terminal 1, repo root: the backend
.venv/Scripts/python -m uvicorn ruko.main:app --port 8000

# terminal 2: the app with hot reload
cd frontend
npm install          # first time only
npm run dev          # http://localhost:5173 (proxies /v1 to :8000)
```

Open http://localhost:5173 in Chrome. For a phone-sized view, press F12 and turn on the device
toolbar at 390 × 844. The first run shows a short welcome (language, your own rules, or "Skip,
use safe defaults").

To see the installable app with its service worker and share target, use the production build
served by the backend instead:

```bash
cd frontend && npm run build && cd ..
# PowerShell
$env:RUKO_STATIC_DIR="frontend/dist"; .venv\Scripts\python -m uvicorn ruko.main:app --port 8000
# bash
RUKO_STATIC_DIR=frontend/dist .venv/Scripts/python -m uvicorn ruko.main:app --port 8000
```

## Try it on an Android phone

1. **Start the built app on the laptop** as shown above, and check that http://localhost:8000
   opens Ruko.
2. **Connect the phone.**
   - **USB (recommended):** turn on Developer options and USB debugging on the phone, connect
     the cable, then open `chrome://inspect/#devices` in the laptop's Chrome. Under **Port
     forwarding**, map 8000 to `localhost:8000`, then open http://localhost:8000 in the phone's
     Chrome.
   - **Tunnel:** run `cloudflared tunnel --url http://localhost:8000` and open the printed
     `https://…` address on the phone.
3. **Install:** in the phone's Chrome menu, tap **Install app**, then open Ruko from its icon.

What to try:

| Do | You should see |
|---|---|
| In WhatsApp or Telegram, long-press a message → Share → Ruko | Ruko opens and checks it straight away |
| Open a screenshot or photo → Share → Ruko | Ruko reads the picture and checks it (needs a Gemini key) |
| Share *Guaranteed 3x return in 7 days. Join our Telegram group, act today!*, then answer ₹20000 / emergency money / scheme | A pause: signals quoting the message, your money against your savings, your own rules, tappable words |
| Learn → open a lesson → tap a dotted word | Swipeable lesson cards; a small pop-up explains the word |
| Work out a number → SIP 5000 for 10 years | Scenarios side by side and a chart, labelled as arithmetic, not a prediction |
| I already paid → Yes → UPI → can't withdraw: Yes | Urgent steps first (1930 is a tap-to-call link), a checklist and a complaint draft to copy |
| Settings → हिन्दी or ಕನ್ನಡ | Every screen switches language |
| Airplane mode, then reopen | Rules and journal still open, with an offline notice |

If an old version ever shows up: Chrome → Settings → Site settings → All sites → localhost →
Clear & reset, then reopen.

## Commands

```bash
npm test             # Vitest, using real backend responses saved in src/fixtures/
npm run typecheck    # tsc
npm run build        # type check + production build
npm run check:size   # gzip sizes against the bundle budget (after a build)

# refresh the fixtures from the real backend (repo root)
.venv/Scripts/python frontend/scripts/capture_fixtures.py
```

## Structure

```
src/types/api.ts        mirror of the backend models (src/ruko/models/)
src/services/api.ts     typed calls to /v1 with timeouts and error categories; validate.ts checks responses at runtime
src/services/device.ts  profile, journal and checklist ticks in local storage (device only)
src/services/profile.ts the profile sent with each request, plus attention counts and the late-night flag
src/services/listen.ts  Ruko's voice via /v1/speak, or the phone's own voice as a fallback
src/state/flow.ts       one reducer: one screen per backend `kind`
src/hooks/useDecisionFlow.ts  wires the reducer, the API, voice and the device store
src/components/         presentation (charts are plain SVG, loaded on demand)
src/screens/            screens; ResultScreen switches on the response `kind`
src/share/              reading what was shared into the app (text, links, photos)
src/mock-broker/        the fictional broker demo (/demo/broker)
src/copy/{en,hi,kn}.ts  the app's own text; the compiler rejects a missing Hindi or Kannada string
src/styles/             design tokens and styles
public/                 manifest (share target), icons, service worker
```

## How the app maps to the backend

| On screen | Component | From the backend |
|---|---|---|
| Shared message | `SharedContent`, `QuotedMessage` | `AnalyzeRequest.input`, `SignalView.quote` |
| "What I see" | `SignalCard` | `signals[]` with certainty, severity and role |
| Your money | `MoneyHero`, `PersonalContextCard` | `decision.exposure`, `rules_text[]`, `numbers_text[]` |
| The pause (L0–L3) | `PauseCard` | `PauseResponse.level`, `headline`, `question` |
| Why this matters | `LearnCard`, `LessonCard`, `LessonShorts` | `cards[]`, `lessons[]` |
| Tappable words | `Terms` | `terms[]` |
| Continue anyway | `ActionButton` | `override_label` (always allowed) |
| Waiting period | `CoolingOffTimer` | `decision.cooling_off_minutes` |
| Calculator | `CalculatorScreen`, `CalculationCard` | `POST /v1/calculate` |
| Learn | `LearnScreens` | `POST /v1/learn`, `POST /v1/learn/lesson` |
| Recovery | `RecoverFormScreen`, `RecoveryGuideView` | `POST /v1/recover` |
| My patterns | `MirrorScreen` | `POST /v1/journal/review` |
| Fictional broker | `mock-broker/BrokerApp` | `POST /v1/order-intent` |

Reflection answers and free-text notes stay on the phone. They have no backend field.

## Sharing, offline and size

- **Share target:** the manifest declares a POST share target for title, text, url and an image.
  The service worker turns text into `/?text=…` and keeps a shared image in a short-lived inbox
  until the app reads and deletes it. If the service worker isn't active yet, the backend hands
  the share back inside the page instead (`src/ruko/api/share.py`).
- **Offline:** pages are network-first, built files cache-first, and `/v1` is never cached.
  Rules, journal and the recovery checklist work offline.
- **Size:** the entry JS stays under 100 KB gzip, checked by `npm run check:size`. The
  calculator, Learn, charts and the broker demo load on demand. No web fonts.
- **Languages:** Hindi and Kannada text is a draft until a native speaker reviews it.
