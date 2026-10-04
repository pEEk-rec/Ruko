# API contract (v1)

All endpoints are JSON over HTTPS, versioned under `/v1` (plus `GET /health`). The
interactive OpenAPI docs at `/docs` are generated from the Pydantic models in
`src/ruko/models/`, which are the source of truth; this page explains them.

General rules:

- **Stateless.** Every request carries what it needs (profile snapshot, journal entries).
  Nothing is stored; message text, audio, profile and results are never logged.
- **Money** is always integer rupees (`amount_inr: 20000`).
- **Locales** are short codes (`en`, `hi`, `kn`). Enabled locales come from configuration.
- **Every response** includes `meta` (request ID, locale, decision stage and who decided it,
  policy/prompt version, extraction mode, unverified fact IDs, draft-template count, missing
  template keys, blocked-output count, and a content-free trace of workflow steps). The
  `x-request-id` header is on every response.
- **Output validation.** Every rendered string passes the assertion-level validator for its
  template's `response_type`, and every text response is checked once more as a whole before
  it leaves (`OUTPUT_BLOCKED` if anything slips through).
- **Unverified facts** are shown in development and hidden in production
  (`show_unverified_facts`); `meta.unverified_fact_ids` lists the ones shown.
- **Override is always allowed.** `decision.override_allowed` is the constant `true`.
- **Responses are discriminated by `kind`**: `pause`, `refusal`, `clarify`,
  `content_report`, `glossary`, `calculation`, `cards`, `recovery`, `journal_review`, `speech`,
  `order_intent`, `meta`.

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

Analyze one shared item (text, link or screenshot). The input guardrail runs first; then the
input gets a decision stage (`docs/decision_stages.md`) and the stage picks the path.

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
  "answers": {"amount_inr": 40000, "funding_source": "borrowed",
              "plan": {"reason_given": true, "horizon": "weeks"}}
}
```

- `input.type`: `text` | `link` | `image` (base64 PNG/JPEG/WebP). Voice uses `/v1/analyze/voice`.
- `answers` holds what the user declared. **Amount and funding source are never inferred**;
  if the engine needs them and they are missing, the response is `clarify`. Answering
  `unknown` ("prefer not to say" / "not sure") counts as an answer; fields listed in
  `answers.skipped_fields` are not asked again (they stay in `event.missing_fields`).
- `answers.calculation` (optional, `CalculationInputs`): calculator inputs the user typed or
  answered (`tool`, `amount_inr`, `monthly_inr`, `goal_inr`, `already_saved_inr`, `months`,
  `years`, `rates_pct[]`, `drops_pct[]`, `leverage`, `trade_value_inr`, `trades_per_month`);
  they win over numbers read from the text.
- `answers.stage` (optional) is the stage the user chose in the app and wins over detection;
  `answers.action` (`buy`, `sell`, `invest`, `pay`, `join`) and `answers.plan` (presence of
  reason / horizon / reconsider condition; the words stay on the device) are optional.
- Clarify order and choices come from `data/policy/clarify.yaml` (amount, funding source,
  product class; at most 3). If the message has a high-severity content signal, the pause is
  returned at once without questions.
- Text is understood by the LLM (when configured) from redacted text only, else by the
  lexicon; `meta.extraction_mode` and `meta.prompt_version` say which ran.

Response: one of (by stage)

- `PauseResponse` (`kind: "pause"`; consider_action / about_to_act): `level`, `headline`,
  `numbers_text[]` (exposure), `rules_text[]`, `signals[]` (each with `certainty`,
  `severity`, `text` = "label: explanation", and the two parts separately as
  `certainty_label` and `reason_text`, so a client can show a badge in any locale without
  repeating it), `question`, `cards[]` (max 3), `lessons[]` (max 2; cards + lessons together max 3),
  `recovery_entry`, `override_label`, `speak[]`,
  `decision` (`InterventionDecision` with `reasons[]` each carrying its `dimension`,
  `content_codes[]`, `behavioural_codes[]`, `dimension_levels {content, behavioural}`,
  `matched_rules[]`), `event` (`stage`, `action`, `product_class`, `source_type`: what the
  decision was about, never message text; for the device journal), `meta`.
- `ContentReportResponse` (`kind: "content_report"`; evaluate_content): `headline` (includes
  "Ruko can't vouch"), `signals[]` (same shape as in the pause), `note` when nothing was found,
  safety-critical `cards[]` and `lessons[]`, `recovery_entry`, `speak[]`, `meta`. No level, no
  verdict.
- `GlossaryResponse` (`kind: "glossary"`; learn): `found`, `term`, `title`, `body`, `sources[]`,
  `speak[]`, `meta`.
- `RecoveryGuide` (`kind: "recovery"`; already_acted): as `/v1/recover`, with answers pre-filled
  from the text (yes/no facts and payment method only).
- `CalculationResponse` (`kind: "calculation"`; calculate): `tool` (`sip`, `goal`, `inflation`,
  `consequence`, `costs`), `inputs` (the numbers used, echoed; no message text), `headline`,
  `explanation` (amounts also in words), `assumptions[]` (always includes "arithmetic under
  assumptions, not a prediction"), `scenarios[]` (two or more: `label`, `assumption_pct`,
  `values` in integer rupees, rendered `lines[]`, yearly `series[]` for SIP),
  `is_illustration: true`, `lessons[]` (max 2), `speak[]`, `meta`. Rates the user did not give come from the
  labelled example sets in `data/policy/calculators.yaml`. Missing required inputs return
  `clarify` with fields `calculation.<name>` (numeric, no options) or `calculation.tool`
  (options); the client sends the answer back in `answers.calculation`. Calculator inputs
  cannot be skipped.
- `RefusalResponse` (`kind: "refusal"`): `refusal_class` (`ADVICE_REQUEST`,
  `PREDICTION_REQUEST`, `INSTRUMENT_EVALUATION`, `BROKER_RECOMMENDATION`, `ROLEPLAY_ADVISOR`,
  `SENSITIVE_DATA_SUBMISSION`), `message`, `alternative`, `speak[]`, `meta`.
- `ClarifyResponse` (`kind: "clarify"`): `questions[]` (`field`, `text`, `options[]`), `event`
  (what was understood so far, evidence removed), `speak[]`, `meta`. The client asks, then
  resends the same request with `answers` filled in. For `unknown` stage the single question
  has `field: "stage"` and five options (`learn`, `evaluate_content`, `consider_action`,
  `already_acted`, `calculate`).

## `POST /v1/analyze/voice`

Same as analyze, but the input is a voice note (`VoiceAnalyzeRequest`):
`audio_base64`, `audio_format` (`wav`, `mp3`, `ogg`, `opus`, `webm`, `m4a`, `aac`, `flac`, `amr`),
`speech_locale` (hint), `locale`, `profile`, `answers`. Audio is decoded and transcribed in
memory, then discarded. Limits: size and duration from settings (`max_audio_bytes`,
`max_audio_seconds`; duration is measured exactly for WAV, other formats are bounded by
size). The declared `audio_format` must match the file's magic bytes. Response: same union
as `/v1/analyze`.

## `POST /v1/speak`

Read Ruko's own text aloud (`SpeakRequest`): `locale` and either `items[]` of `{key, slots}`
taken from a previous response's `speak[]`, or `lesson_id` (title and plain body of one
lesson; exactly one of the two; an unknown or production-hidden lesson is `INVALID_REQUEST`). The server re-renders each template, runs the output
filter, then calls TTS. Free text is not accepted, and slot values must be number-like
(digits, `₹`, `%`, number punctuation; `data/policy/speech.yaml`). Items are kept whole up
to the provider's text limit. Response (`SpeakResponse`):
`audio_base64`, `audio_format`, `provider`, `meta`.

## Adaptive fields (A to F work)

- `SignalView.quote`: a short excerpt of the **user's own message** (redacted: contact details
  appear as placeholders) that the signal rests on, so an app can show "from your message". It
  is a plain substring of the redacted text, at most 140 characters, only for signals found in
  the message (not for the user's own rules or funding), never validated as Ruko wording, never
  logged and never spoken. It travels only back to the person who sent the message.
- `ClarifyQuestion.hints[]`: values the message itself mentions (for the amount question, "The
  message mentions ₹5,000"), offered as one-tap confirmations. An amount is never applied
  without the user tapping it. `ClarifyQuestion.suggested` / `suggested_tag`: the answer choice
  that matches what the message describes gets a tag; all choices are still offered.
- `PauseResponse.refine[]`: when a high-severity message was shown before any question, the
  pause carries the unanswered questions (with hints) so the app can ask them inline; answering
  re-runs the analysis and fills "your context".
- `PauseResponse.numbers_text` at L1 now holds the amount and its share of savings (a "brief"
  numbers line), so an amount the user typed is never invisible.
- **Learn (new).** `POST /v1/learn` (`{locale, profile}`) returns `LearnHubResponse`
  (`kind: "learn_hub"`: `featured`, `read_count`, `total`, `topics[]` of lessons with `id`, `title`,
  `summary`, `read_seconds`, `seen`, and `words[]` of `{id, title, brief}`). `POST /v1/learn/lesson`
  (`{locale, lesson_id, profile}`) returns `LessonResponse` (`kind: "lesson"`: `lesson` with
  `summary`, `own_guidance`; `next`; `terms`). An unknown or production-hidden lesson is
  `INVALID_REQUEST`. The profile only decides ordering (`seen_lesson_ids`, `experience`,
  `recent.post_loss`, `recent.trades_this_week`, `recent.late_night`).
- **Word layer (new).** `terms[]` (`{id, match, title, brief}`) on `pause`, `content_report`,
  `calculation`, `refusal`, `glossary` and `lesson` responses: every glossary word used in the
  response's own rendered text (never the user's quote), one entry per wording. `learn_next`
  (`{id, title, summary, read_seconds, topic, seen, safety_critical}`) on quiet pauses, content
  reports, calculations and glossary answers. `SignalView.role` and `role_label` group signals.
- `GlossaryResponse.related[]`: other terms Ruko can explain, `{id, title}`; the title is also
  the question to send to ask about that term.
- `POST /v1/calculate` (`CalculateRequest`: `locale`, `inputs` as `CalculationInputs`, optional
  `profile`): the live calculator. Returns a `calculation` (at least two scenarios, the user's own
  rates kept next to the labelled examples, assumptions, `is_illustration: true`, lessons) or a
  `clarify` for a missing required number. Same numbers as the text path; out-of-range input is
  a 422 that never echoes the value.

## Lessons (`lessons[]`)

A `Lesson` is a short curated micro-lesson chosen for this decision (`data/learn/lessons.yaml`):
`id`, `title`, `body` (about 60 to 120 words, the user's own rupees where the lesson has an
amount version), `read_seconds`, `safety_critical`, `related_tool` (a calculator the app may
offer), `as_of`, `sources[]`, `verified_by_human`, `speak[]` (the references to read it, also
available as `lesson_id` on `/v1/speak`). Selection is deterministic: at most 2 lessons per
response and at most 3 explanation items (cards + lessons); a lesson replaces the card about
the same topic; seen lessons (`profile.seen_lesson_ids`) fade unless safety-critical; in
production only lessons whose text and cited facts are all verified by a human are shown. The
LLM never writes lesson text. `UserProfile.seen_lesson_ids` is the new device field.

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
optional `as_of` date. Entries carry stage, level shown, reasons, action (`went_ahead`,
`changed_amount`, `delayed`, `set_plan`, `dropped`), override and whether a reason was given,
pause completed, could state why, plan parts present and followed, own rules/plans count.
Response (`kind: "journal_review"`): the impact metrics of `docs/impact_metrics.md`
(unsolicited share, plans set/followed, pause completion, comprehension, reconsideration,
overrides with/without reason, rule articulation), weekly interventions-per-decision points
(data, not a score), rendered `highlights[]`, `meta`. Nothing is kept.

## `POST /v1/order-intent` (broker embedding)

For brokers who embed Ruko before order placement. See `docs/broker_embedding_spec.md`.
Request (`OrderIntentRequest`): `product_class`, `amount_band` (`min_inr`, `max_inr`),
`borrowed_funds`, `leveraged`, `plan_matched` (the order follows a plan the user logged;
optional),
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
