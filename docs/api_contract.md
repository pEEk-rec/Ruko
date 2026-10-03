# API contract (v1)

All endpoints are JSON over HTTPS, versioned under `/v1` (plus `GET /health`). The
interactive OpenAPI docs at `/docs` are generated from the Pydantic models in
`src/ruko/models/`, which are the source of truth; this page explains them.

General rules:

- **Stateless.** Every request carries what it needs (profile snapshot, journal entries).
  Nothing is stored; message text, audio, profile and results are never logged.
- **Money** is always integer rupees (`amount_inr: 20000`).
- **Locales** are short codes (`en`, `hi`, `kn`). Enabled locales come from configuration.
- **Every response** includes `meta` (request ID, locale, policy/prompt version, extraction
  mode, unverified fact IDs, draft-template count, missing template keys, blocked-output count,
  and a content-free trace of workflow steps). The `x-request-id` header is on every response.
- **Override is always allowed.** `decision.override_allowed` is the constant `true`.
- **Responses are discriminated by `kind`**: `pause`, `refusal`, `clarify`, `cards`,
  `recovery`, `journal_review`, `speech`, `order_intent`.

## Errors

```json
{"error": {"code": "INVALID_REQUEST", "message_key": "error.invalid_request", "retryable": false, "fields": ["body.input.type"]}}
```

`fields` appears only for validation errors and lists field locations, never values.
Error responses never echo input.

| Code | HTTP | Retryable | When |
|---|---|---|---|
| `INVALID_REQUEST` | 422 | no | Body fails validation |
| `NOT_FOUND` | 404 | no | Unknown route |
| `METHOD_NOT_ALLOWED` | 405 | no | Wrong method |
| `PAYLOAD_TOO_LARGE` | 413 | no | Body over the configured limit |
| `UNSUPPORTED_MEDIA_TYPE` | 415 | no | Not JSON |
| `RATE_LIMITED` | 429 | yes | Too many requests from one client |
| `LOCALE_UNSUPPORTED` | 422 | no | Locale not enabled |
| `LLM_UNAVAILABLE` | 503 | yes | (internal; analyze falls back to the lexicon instead) |
| `LLM_INVALID_OUTPUT` | 502 | yes | (internal; analyze falls back to the lexicon instead) |
| `OCR_UNAVAILABLE` | 503 | yes | Image sent but no OCR provider is configured |
| `SPEECH_UNAVAILABLE` | 503 | yes | No speech provider available |
| `AUDIO_TOO_LARGE` / `AUDIO_TOO_LONG` | 413 | no | Audio over size or duration limit |
| `AUDIO_FORMAT_UNSUPPORTED` | 415 | no | Unknown audio format or undecodable base64 |
| `IMAGE_TOO_LARGE` | 413 | no | Image over size limit |
| `IMAGE_FORMAT_UNSUPPORTED` | 415 | no | Not PNG/JPEG/WebP or undecodable base64 |
| `TOOL_NOT_ALLOWED` | 500 | no | Workflow tried a tool outside the allow-list (a bug) |
| `TOOL_FAILED` | 502 | yes | A required tool failed |
| `OUTPUT_BLOCKED` | 500 | no | Output filter blocked text and no safe fallback existed |
| `INTERNAL_ERROR` | 500 | yes | Anything unexpected |

## `GET /health`

`{"status": "ok", "version": "0.1.0"}`

## `POST /v1/analyze`

Analyze one shared item (text, link or screenshot).

Request (`AnalyzeRequest`):

```json
{
  "input": {"type": "text", "content": "BANKNIFTY CE buy now, 300% sure!!", "claimed_locale": "en"},
  "locale": "en",
  "profile": {
    "monthly_expenses_band": "25k_50k",
    "liquid_savings_band": "1l_3l",
    "rules": {"max_share_of_savings_pct": 10, "no_borrowed_money": true},
    "experience": {"derivative": "none"},
    "age_band": "lt_30"
  },
  "answers": {"amount_inr": 40000, "funding_source": "borrowed"}
}
```

- `input.type`: `text` | `link` | `image` (base64 PNG/JPEG/WebP). Voice uses `/v1/analyze/voice`.
- `answers` holds what the user declared. **Amount and funding source are never inferred**;
  if the engine needs them and they are missing, the response is `clarify`. Answering
  `unknown` ("prefer not to say" / "not sure") counts as an answer; fields listed in
  `answers.skipped_fields` are not asked again (they stay in `event.missing_fields`).
- Clarify order and choices come from `data/policy/clarify.yaml` (amount, funding source,
  product class; at most 3). If the message has a strong fraud pattern, the pause is
  returned at once without questions.
- Text is understood by the LLM (when configured) from redacted text only, else by the
  lexicon; `meta.extraction_mode` and `meta.prompt_version` say which ran.

Response: one of

- `PauseResponse` (`kind: "pause"`): `level`, `headline`, `numbers_text[]`, `rules_text[]`,
  `signals[]` (each with `certainty`), `question`, `cards[]` (max 3), `recovery_entry`,
  `override_label`, `speak[]`, `decision` (`InterventionDecision`), `meta`.
- `RefusalResponse` (`kind: "refusal"`): `refusal_class` (`ADVICE_REQUEST`,
  `PREDICTION_REQUEST`, `INSTRUMENT_EVALUATION`, `BROKER_RECOMMENDATION`, `ROLEPLAY_ADVISOR`,
  `SENSITIVE_DATA_SUBMISSION`), `message`, `alternative`, `speak[]`, `meta`.
- `ClarifyResponse` (`kind: "clarify"`): `questions[]` (`field`, `text`, `options[]`), `event`
  (what was understood so far), `speak[]`, `meta`. The client asks, then resends the same
  request with `answers` filled in.

## `POST /v1/analyze/voice`

Same as analyze, but the input is a voice note (`VoiceAnalyzeRequest`):
`audio_base64`, `audio_format` (`wav`, `mp3`, `ogg`, `opus`, `webm`, `m4a`, `aac`, `flac`, `amr`),
`speech_locale` (hint), `locale`, `profile`, `answers`. Audio is decoded and transcribed in
memory, then discarded. Limits: size and duration from settings (`max_audio_bytes`,
`max_audio_seconds`; duration is measured exactly for WAV, other formats are bounded by
size). The declared `audio_format` must match the file's magic bytes. Response: same union
as `/v1/analyze`.

## `POST /v1/speak`

Read Ruko's own text aloud (`SpeakRequest`): `locale` and `items[]` of `{key, slots}` taken
from a previous response's `speak[]`. The server re-renders each template, runs the output
filter, then calls TTS. Free text is not accepted, and slot values must be number-like
(digits, `₹`, `%`, number punctuation; `data/policy/speech.yaml`). Items are kept whole up
to the provider's text limit. Response (`SpeakResponse`):
`audio_base64`, `audio_format`, `provider`, `meta`.

## `POST /v1/cards`

Cards for a given event and profile (`CardsRequest`: `locale`, `event`, `profile`).
Response (`CardsResponse`): `cards[]` (max 3), `meta`.

## `POST /v1/recover`

Recovery guide (`RecoverRequest`): `locale`, `answers` (`paid_money`, `payment_method`,
`installed_app`, `registered_broker_involved`, `unauthorized_trade`, `cannot_withdraw`).
Response (`RecoveryGuide`, `kind: "recovery"`): `scenario` (`paid_scammer`,
`suspicious_app_installed`, `registered_broker_issue`, `unauthorized_trade`, `cannot_withdraw`,
`no_loss_yet`), ordered `steps[]` (urgent first,
each with official `contact`), `evidence_checklist[]`, `draft_complaint` (the user copies and
sends it; Ruko never submits), `sources[]`, `speak[]`, `meta`.

## `POST /v1/journal/review`

Patterns from the device journal (`JournalReviewRequest`): `locale`, `entries[]` (max 1000),
optional `as_of` date. Response (`kind: "journal_review"`): counts and percentages (share of
tip-driven decisions, exit plans set and followed, overrides), weekly
interventions-per-decision trend and its direction, rendered `highlights[]`, `meta`.
Numbers and template text only; nothing is kept.

## `POST /v1/order-intent` (broker embedding)

For brokers who embed Ruko before order placement. See `docs/broker_embedding_spec.md`.
Request (`OrderIntentRequest`): `product_class`, `amount_band` (`min_inr`, `max_inr`),
`borrowed_funds`, `leveraged`, `exit_plan_set` (e.g. a stop-loss is attached; optional),
`profile`. No instrument identity, no user ID.
Response (`OrderIntentResponse`): `level`, `reason_codes[]`, `override_allowed: true`,
`policy_version`. No text, no advice.

## Edge rules (all `/v1` routes)

- Bodies must be `application/json` (else `415`) and at most `max_request_bytes` (else `413`).
- Rate limit: `rate_limit_per_minute` requests per client per minute (else `429`); `/health`
  is not limited. Clients are keyed by a salted hash of their address, kept in memory for the
  current minute only.
- CORS is off unless `cors_allow_origins` is set.
- Pause content by level: L0 headline only; L1 adds the top reason and one question; L2/L3
  add your numbers, your rules, every reason with its certainty, and up to 3 cards.

## `GET /v1/meta`

Supported and enabled languages, template counts by status per locale, every displayed fact
with its verification status and `as_of` date, policy and prompt versions, and which
providers are configured (true/false only, never keys).
