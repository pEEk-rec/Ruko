# Ruko (backend)

Ruko is a decision-safety layer for Indian retail investors, built for the SANGYAN Investor
Resilience Hackathon (SNTC, IIT (BHU) Varanasi, with SEBI and NSDL), Track D: Financial Habits
& Behavioural Resilience.

Financial tips reach people through Telegram, WhatsApp, YouTube and friends. Both kinds of harm,
self-inflicted losses in the real market and fraud in fake "markets", start from the same
forwarded message. Ruko sits at the moment between "I want to act" and "I acted". It shows only
what this decision means for **the user's own money, rules and plan**, in English, Hindi or
Kannada, then steps back, and routes the user to official help if something already went wrong.

**Ruko is not** an investment adviser, a tip rater, a trading tool, a chatbot that answers
"should I buy X", or a course. It never says a tip, scheme, app or person is good, bad, safe or
legit, and it never blocks: every pause can be overridden.

## How a message flows

```
              SOCIAL / PEER CONTENT (Telegram, WhatsApp, YouTube, friends)
                                   │  share / paste / voice / screenshot
┌──────────────────────────── RUKO BACKEND (stateless) ───────────────────────────┐
│ 1. Input adapters      text · link (never fetched) · screenshot → OCR · voice → STT│
│ 2. Language + redact   language/script detection; phone, UPI, account, card,     │
│                        email, PAN, names removed LOCALLY before any external call  │
│ 3. Input guardrail     refuses advice / prediction / evaluation / broker /       │
│                        role-play requests and pasted OTPs, PINs, passwords        │
│ 4. Decision stage      learn · evaluate_content · consider_action · about_to_act  │
│                        · already_acted · unknown  (patterns first; LLM fills gaps)│
│ 5. Understand          lexicons, link and payment checks; LLM extraction as a     │
│                        helper (redacted text only; works without it)              │
│ 6. Route by stage      glossary │ content report │ engine → pause │ recovery │ ask│
│ 7. Safety engine       two dimensions: content signals + the user's own context   │
│    (deterministic)     → L0 pass · L1 nudge · L2 pause · L3 strong pause          │
│ 8. Cards               0-3 just-in-time explanations, cited and dated, fade once  │
│                        seen (scam cards never fade)                               │
│ 9. Render + validate   localized templates only; assertion-level output validator │
│                        on every string and once more on the whole response        │
└─────────────────────────────────────────────────────────────────────────────────┘
       Side paths: recovery routing · journal review (impact metrics) · broker API
```

The LLM never decides the stage over the patterns, the level, the reasons, the numbers or any
user-facing text. Everything the user reads comes from human-written templates.

## Run locally

Requires Python 3.11+.

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"     # on macOS/Linux: .venv/bin/python
.venv/Scripts/python -m uvicorn ruko.main:app --reload
```

Open http://127.0.0.1:8000/docs for the interactive API, or http://127.0.0.1:8000/health.

Configuration comes from `RUKO_*` environment variables or a local `.env` (copy `.env.example`).
Ruko runs without any keys: extraction falls back to the deterministic lexicon, and speech
endpoints return a typed `SPEECH_UNAVAILABLE` error while the text path keeps working.

| Setting | Meaning |
|---|---|
| `RUKO_ENVIRONMENT` | `dev`, `test` or `prod` (prod hides unverified facts) |
| `RUKO_SHOW_UNVERIFIED_FACTS` | override the above (`true`/`false`) |
| `RUKO_LLM_PROVIDER` | `auto` (Gemini if a key is set), `gemini`, `fake`, `none` |
| `RUKO_GEMINI_API_KEY`, `RUKO_GEMINI_MODEL` | Gemini key and model |
| `RUKO_SPEECH_PROVIDERS`, `RUKO_SARVAM_API_KEY` | speech fallback order and Sarvam key |
| `RUKO_ENABLED_LOCALES` | default `en,hi,kn` |
| `RUKO_CORS_ALLOW_ORIGINS`, `RUKO_RATE_LIMIT_PER_MINUTE` | HTTP edge |

## Run with Docker

```bash
docker build -t ruko .
docker run --rm -p 8000:8000 --env-file .env ruko      # the image defaults to RUKO_ENVIRONMENT=prod
```

## Test, lint, evaluate

```bash
.venv/Scripts/python -m pytest                       # main suite: offline, fake providers
.venv/Scripts/python -m pytest -m live               # optional live checks (needs keys)
.venv/Scripts/python -m ruff check . && .venv/Scripts/python -m ruff format --check .
.venv/Scripts/python eval/run_eval.py                # writes docs/eval_report.md
```

The suite includes a 120+ case multilingual adversarial guardrail suite, an assertion-level
output-validator suite, 16 golden end-to-end scenarios,
property tests on the engine, template linting (every string passes the output validator in all
three languages) and security/privacy tests.

## API overview (`/v1`)

| Endpoint | What it does |
|---|---|
| `POST /v1/analyze` | Text, link or screenshot → pause, refusal, clarify, content report, glossary or recovery guide (by decision stage) |
| `POST /v1/analyze/voice` | Voice note → transcribed in memory → same as analyze |
| `POST /v1/speak` | Reads Ruko's own templates aloud (no free text) |
| `POST /v1/cards` | Just-in-time cards for an event and profile |
| `POST /v1/recover` | Recovery guide: urgent steps first, evidence checklist, draft complaint (the user sends it) |
| `POST /v1/journal/review` | The user's own patterns from their device journal |
| `POST /v1/order-intent` | Broker embedding: level and reason codes only, no instrument, no user ID |
| `GET /v1/meta` | Languages, template status, fact verification status, versions, providers |

Details: `docs/api_contract.md`, `docs/broker_embedding_spec.md`.

## Privacy and data flow

- The **profile, rules, plans and journal live on the device** and travel with each request.
  The server is stateless: it stores nothing and never logs message text, audio, profiles or
  results. Log lines are built from an allow-list of fields (request ID, route template, status,
  timings, stage, reason and error codes), checked by tests.
- **Before any external call**, personal data in text is redacted locally; only redacted text is
  sent to the LLM. Screenshots and voice notes are the exception: an image or audio cannot be
  redacted before it is read, so they reach the OCR / speech provider as they are, in memory only
  (see `docs/production_path.md`).
- Links in messages are analyzed as strings and **never fetched**. Ruko never sends messages on
  the user's behalf and never touches money.

## Third-party components (disclosure)

| Component | Use | Where |
|---|---|---|
| Google Gemini, via the official Google Gen AI SDK (`google-genai`) | Structured extraction from redacted text; screenshot OCR | `src/ruko/providers/llm/gemini.py` |
| Sarvam AI REST API | Speech-to-text and text-to-speech (Kannada, Hindi, English) | `src/ruko/providers/speech/sarvam.py` |
| Bhashini | Not used (reserved as a second speech provider; no credentials) | — |
| FastAPI, Uvicorn, Pydantic, PyYAML, httpx | Web service, validation, data files, HTTP client | `pyproject.toml` |
| pytest, hypothesis, ruff | Tests, property tests, lint (development only) | `pyproject.toml` |

Facts shown to users come from primary sources (SEBI studies and circulars, the National Cyber
Crime Reporting Portal / I4C, SEBI SCORES) listed with their verification status in
`docs/data_sources.md`.

## Limitations (stated plainly)

- **No fact is verified by a human yet.** In production every unverified fact is hidden,
  including recovery contacts such as 1930, until the owner verifies `data/facts/`.
- **Hindi and Kannada texts, lexicons and stage patterns are drafts** awaiting native review.
- **The deterministic guardrail misses unseen phrasings**: on the held-out set it refused 6 of 16
  advice/secret inputs before generalisation (`docs/eval_report_heldout_baseline.md`). Ruko
  still never outputs advice (every output is a validated template), but a refusal can become a
  clarifying question instead.
- **Evaluation data is synthetic** and written by the same author as the patterns, so results
  are optimistic; the LLM-on evaluation has not been run (free-tier quota).
- **Ruko cannot see trades or bank accounts**; behaviour signals are self-declared.
- The Gemini key used in testing is free tier (5 requests/minute); live checks were partial.

More: `docs/production_path.md`, `docs/open_questions.md`, `docs/decisions.md`.
