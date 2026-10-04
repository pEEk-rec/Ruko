# Production path

> Statements about third-party services that are not sourced here are marked **TODO_VERIFY**.

## Why the prototype uses Gemini and Sarvam

- **Gemini** (Google Gen AI SDK) does one narrow job: turn redacted, messy text into a small
  JSON object (stage, product class, action, source type, payment-destination type, content
  signals with exact quotes) and transcribe screenshots. It was chosen because it is available,
  handles English, Hindi and Kannada, and returns JSON. Nothing in Ruko depends on Gemini
  specifically: it sits behind `LLMProvider` (`src/ruko/providers/llm/base.py`).
- **Sarvam** does speech-to-text and text-to-speech for Indian languages behind `STTProvider` /
  `TTSProvider` (`src/ruko/providers/speech/`). Bhashini can be added as a second provider in the
  configured fallback order once credentials exist.

## The LLM's role is narrow by design

| | The LLM does | The LLM never does |
|---|---|---|
| Input | Reads **redacted** text (phone numbers, UPI IDs, emails, PAN, account and card numbers, names after salutations replaced locally first) | Sees raw personal data (except screenshots for OCR, see below) |
| Output | Fills a JSON form validated by Pydantic; proposes content signals with verbatim quotes | Writes any user-facing text (v1), decides the stage over a deterministic result, the level, reason codes or numbers |
| Failure | Retried once with the validation error, then ignored | Breaks the pipeline: everything runs on lexicons and rules without it (`extraction_mode: lexicon_only`) |

Because the task is small (a few hundred input tokens, a short JSON reply), a production
deployment can use a smaller or self-hosted model without changing any other component.

## Privacy and data residency

- **Stateless server.** Profiles, rules, plans and journals live on the device and travel with
  each request; nothing is stored or logged (allow-listed structured logs only).
- **Local redaction before any external call** (`language/redact.py`), proven by property
  tests over generated phone numbers, UPI IDs and long numbers.
- **Known gap: screenshots and voice notes** reach the OCR / speech provider as they are,
  because an image or audio cannot be redacted before it is read. A production client could do
  on-device OCR and speech-to-text and send only text. TODO_VERIFY: on-device options and
  their Kannada/Hindi quality.
- **DPDP Act, 2023.** Ruko's design (no storage, purpose-limited processing, no profiling across
  users) is intended to keep obligations small, but how the Digital Personal Data Protection Act
  and its rules apply to a deployment must be checked by someone qualified. TODO_VERIFY.
- **Data residency.** Whether prompts sent to a provider are processed or retained outside
  India depends on the provider's terms and region settings. TODO_VERIFY for each provider and
  plan before production.

## Options for a production deployment

| Option | What changes | Notes |
|---|---|---|
| Keep a hosted LLM, paid tier | Only `RUKO_GEMINI_MODEL` / key | Removes the free-tier rate limit seen in testing (5 requests/minute). |
| Indian-hosted inference of an open model | A new `LLMProvider` class | TODO_VERIFY: available Indic-capable open models and hosting options. |
| Bhashini for speech (and possibly translation) | A new `BhashiniProvider` in the speech chain | Government language infrastructure; needs credentials. TODO_VERIFY: terms, latency, Kannada voices. |
| No LLM at all | `RUKO_LLM_PROVIDER=none` | Works today; lower recall on messy phrasing (see `docs/eval_report.md`, LLM-off section). |

## Cost per request (order of magnitude)

Extraction is one call per analyzed message (none for refusals, glossary questions and
already-acted reports), with roughly 1,500 input tokens (mostly the fixed system prompt) and a
short JSON reply. TODO_VERIFY: current per-token prices of the chosen provider; prompt caching
of the fixed system prompt could reduce cost further.

## Before going live (checklist)

1. A human verifies every fact in `data/facts/` (all are `verified_by_human: false` today);
   production hides unverified facts (`show_unverified_facts: false`), which currently hides the
   recovery contacts too.
2. Native speakers review Hindi and Kannada templates, lexicons and stage patterns.
3. Paid or self-hosted LLM and a speech key; live checks re-run.
4. A host chosen (Cloud Run steps are in `deploy_cloud_run.md`), keep-warm configured, CORS set to the real
   frontend origin.
