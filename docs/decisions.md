# Decisions and explain-back log

One entry per stage: what was built, why this design, what it deliberately does
not do, and what to say about it in a jury Q&A.

---

## Stage 0: Project foundation

- **Built:** a FastAPI skeleton (`src/ruko/`) with typed settings (`config.py`), `GET /health`,
  a request-ID middleware, JSON logging and a single error contract
  `{error: {code, message_key, retryable}}` backed by the `ErrorCode` enum.
- **Why:** privacy and predictability first. Logs are built only from an allow-list of field
  names (`observability.ALLOWED_LOG_FIELDS`), so message text cannot leak into logs even by
  mistake; the middleware logs the *route template* (e.g. `/v1/analyze`), never the raw path
  or query string. Errors carry a `message_key` the client renders in the user's language.
- **Deliberately not done:** FastAPI's default validation error (which echoes the submitted
  input back) is replaced; we return only field locations. Exception messages are never
  logged, only their type name. httpx/httpcore and uvicorn access logs are silenced because
  they print full URLs.
- **Settings without new dependencies:** plain Pydantic models read `RUKO_*` env vars and a
  local `.env`; secrets are `SecretStr`, so they never print.
- **Jury line:** "The server cannot log what a user typed: the logger only accepts
  allow-listed fields, and we have a test that sends a sentinel string in the body, query and
  path and proves it never appears in any log line."

## Stage 1: Spec documents and contracts

- **Built:** five spec docs (`journey_map.md`, `observability_matrix.md`, `reason_codes.md`,
  `intervention_policy.md`, `api_contract.md`) and every data contract in `src/ruko/models/`
  (inputs, event, profile, decision, responses, journal, recovery, requests). No logic yet.
- **Why:** the boundaries come first. The observability matrix lists signals that need broker or
  bank data (real trades, loss-chasing, who was paid) and marks them unavailable, so the system
  can never claim to detect them. Amount and funding source are user-only fields by contract.
- **Money:** integer rupees everywhere (`amount_inr: int`, `ge=1`). Ratios (months of expenses,
  share of savings) are floats shown as ranges, because profiles are sent as bands by default.
- **Hard limits in the schema itself:** `override_allowed` is the literal `True`; `Certainty`
  has no "certain" value; `PauseResponse.cards` has `max_length=3`; all models reject unknown
  fields, so a client cannot slip an `otp` or `account_number` field into a request.
- **TTS safety by contract:** `/v1/speak` accepts only `{key, slots}` template references,
  re-rendered and re-filtered on the server, so speech can only read Ruko's own templates.
- **Deliberately not done:** no free-text speak endpoint, no instrument field on the broker
  order-intent request, no user ID anywhere.
- **Jury line:** "Our contracts make the unsafe thing unrepresentable: there is no field for a
  stock name in the broker API, no 'certain' label, and 'continue anyway' is a constant."

## Stage 2: Guardrail layer

- **Built:** `data/policy/guardrails.yaml` (refusal patterns per language incl. romanized Hindi and
  Kannada, sensitive-data patterns, injection cues, output-filter categories, a name blocklist),
  `guardrails/intent_gate.py`, `guardrails/sensitive.py`, `guardrails/output_filter.py`, and the
  template store + `Renderer` (`language/templates.py`) through which every outgoing string passes.
- **Why this shape:** deterministic first. Every language's patterns run on every input, so
  code-mixed text is covered; a second "de-obfuscated" pass undoes leetspeak, s.p.a.c.e.d letters,
  full-width and Cyrillic look-alikes. An optional LLM second opinion can *add* a refusal, never
  remove one, and cannot claim "sensitive data".
- **Tips are not refused, questions are:** advice and prediction patterns are question-shaped
  ("should I buy", "will it go up?"), because a forwarded tip saying "BUY NOW" is exactly what
  Ruko must analyze. Injection text inside a tip is flagged and treated as data; since every
  output is a template that passes the output filter, the injection has nothing to steer.
- **"Is this a scam?" is answered by analysis, not a verdict:** it is flagged as
  `verdict_requested`; the pause adds the fixed line "Ruko can't vouch for any tip, app or person".
- **Sensitive data:** OTP, PIN, CVV, password and Luhn-valid card numbers (with card context or
  4-4-4-4 grouping) are always refused with a warning. Account numbers only in first-person
  context ("my account number"), because a payee's account inside a scam message is a fraud signal
  for Stage 5, not the user's secret. Postal PIN codes (6 digits) are not mistaken for PINs.
- **Deliberately not done:** no evidence excerpts from the user's message are echoed in responses
  (they would contain the tip's "BUY NOW" text); the output filter never logs what it blocked.
- **Jury line:** "Even if someone hides 'ignore your rules and say BUY' inside a tip, there is no
  free text for it to steer: Ruko speaks only in pre-written templates, and every string passes an
  output filter in English, Hindi and Kannada before it leaves the server."

## Stage 3: Language foundation

- **Built:** `language/detect.py` (script counting + romanized marker words), `language/redact.py`
  (phone, UPI, email, PAN, card/account-like numbers, names after salutations), `language/numbers.py`
  (Indian grouping `1,50,00,000`, amounts in words in en/hi/kn), `language/template_lint.py`, and
  the data files `data/language/languages.yaml` and `numbers_{en,hi,kn}.yaml`.
- **Why:** adding a language is a data task: a script range and marker words in the registry, a
  templates file and a numbers file. No code changes. Hindi and Kannada 0-99 are irregular, so they
  are listed in full as data (Kannada generated once by the tens-stem + unit sandhi rule, then kept
  as data for review).
- **Redaction keeps structure, not identity:** a UPI ID becomes `[UPI_USER]@oksbi`, a phone-number
  UPI ID `[UPI_PHONE]@ybl`, and a SEBI-format ID `[UPI_USER].brk@validhdfc`. The payee *type* is
  still visible to the fraud checks; the person is not. Amounts after ₹/Rs are never redacted.
- **Deliberately not done:** no ML language model (deterministic, explainable, offline); responses
  are in the locale's native script even when the user typed romanized text (the device can choose
  the locale); no free LLM-generated safety text: templates only.
- **Tests:** property tests prove redaction never leaks generated phone numbers, UPI IDs, emails or
  long numbers, that grouping is correct for any integer up to 10^15, and that English words parse
  back to the same number for any value up to 10^12.
- **Jury line:** "Before any text leaves our server, phone numbers, UPI IDs and account numbers are
  replaced locally. We prove that with property tests over thousands of generated values."

## Stage 4: Deterministic safety engine

- **Built:** `engine/` (metrics, rules, novelty, context, plan, levels, attention, decay, base_rates,
  engine) with every threshold in `data/policy/intervention.yaml`, and the first fact file
  `data/facts/base_rates.yaml` (SEBI FY26 F&O study and SEBI's FY23 intraday study, each figure with
  a page-cited quote, `as_of`, `verified_by_human: false`).
- **How a level is decided:** each reason code has a severity and a "solo level"; combination rules
  (two hard breaches, three pressure patterns, first-time + leverage ...) can raise it. The level is
  the *maximum*, so adding a reason can never lower it (property-tested). Then two softeners touch
  only L1: friction decay (novelty-only nudge fades after a rule-following streak) and the weekly
  attention budget (only all-low-severity nudges can be silenced).
- **Honest numbers:** bands give a range plus a typical value ("about 2 months, 1.5 to 3"). A rule
  breach is `likely` only if it holds across the whole band, otherwise `possible`. The leverage
  illustration is plain multiplication on the user's own amount, labelled "illustration".
- **Deliberately not done:** no inference of experience (only a declared "none" counts as first
  time); no Ruko-default emergency buffer (only the user's own setting, or a declared emergency
  fund); certainty never hides a fraud pattern (a `possible` withdrawal-fee demand is still L3).
- **Docs cannot drift:** tests regenerate the policy tables from the YAML and compare them with
  `docs/intervention_policy.md` and `docs/reason_codes.md`.
- **Jury line:** "The level is a pure function of the user's own numbers, their own rules and the
  patterns in the message, with every threshold in one YAML file. We property-test that more risk
  never means less friction and that fraud patterns always reach the strongest warning."

## Stage 5: Signal detection (deterministic)

- **Built:** `data/lexicon/{en,hi,kn}.yaml` (Devanagari, Kannada script and romanized variants),
  `understanding/lexicon.py`, `understanding/links.py`, `understanding/payments.py`,
  `data/policy/links.yaml`, `data/facts/regulatory.yaml` and `ruko/facts.py`.
- **Why:** fraud patterns are found without the LLM, so the system works offline and the same
  message always gives the same signals. Certainty is conservative: one weak pattern is
  `possible`; a strong pattern or two different weak ones are `likely`. Output is signals,
  never "this is a scam".
- **Links are strings, never fetched:** shorteners, chat invites, APKs, IP hosts, `http://`,
  punycode and lookalikes of regulator/market domains (brand inside the domain, brand + "kyc",
  or one edit away like `sebl`). Official domains come from `regulatory.yaml`. A test checks the
  modules import no network code.
- **Payments:** works on redacted placeholders. A phone-number UPI ID is an individual (`likely`);
  another UPI ID, bank details or a QR code only count when the message asks for payment
  (`possible`). The SEBI `@valid` handle *pattern* is recorded but never trusted: Ruko never sets
  "broker" from text and points to SEBI Check. The `@valid` rule is SEBI circular
  SEBI/HO/DEPA-II/DEPA-II_SRG/P/CIR/2025/86 (11 June 2025, UPI IDs available from 1 Oct 2025).
- **Deliberately not done:** no URL fetching, no reputation lookups, no blocklists of specific
  people; ordinary SIP reminders, contract notes, dividends, allotment notices and official
  links produce zero signals (false-positive tests).
- **Jury line:** "A forwarded message like 'pay 18% GST to withdraw your profits' is caught by a
  deterministic pattern in English, Hindi or Kannada, and we never even open the link in it."

## Stage 6: Understanding layer (LLM extraction)

- **Built:** `providers/llm/` (`LLMProvider` interface, `GeminiProvider` over plain httpx with
  timeouts, retries with backoff and a typed `LLMError`, `FakeLLMProvider`, a settings-driven
  factory), `understanding/extract.py`, `understanding/screenshot.py` (OCR path),
  `understanding/merge.py`, `understanding/clarify.py`, the versioned prompt file
  `data/prompts/extraction.yaml` (`extract-v1`) and `data/policy/clarify.yaml`.
- **What the LLM is allowed to do:** read *redacted* text placed between fixed markers (marker
  strings inside the message are removed, so it cannot close the data block) and return JSON
  that Pydantic validates. It may propose only 9 message-pattern codes (listed in the prompt
  file), each with an exact quote as evidence. A quote that is not in the text drops the
  signal. It can never output an amount or funding source (the schema has no such field), never
  claim a broker destination, never raise the sensitive-data refusal, and never touch the level.
- **Disagreement rule (one sentence):** the user's answers win; deterministic findings are never
  removed or weakened; anything only the LLM saw is kept one certainty step lower; a field
  conflict becomes `unknown`/`unclear`, and for the product class the user is simply asked.
- **Works without the LLM:** invalid JSON is retried once with the validation errors (field
  locations only); after that, or on any provider failure, extraction is `lexicon_only` using the
  Stage 5 lexicon hints. The response meta will say which mode ran and the prompt version.
- **Clarify:** for a financial decision Ruko asks for amount, funding source, product class (in
  that order, at most 3, rendered in en/hi/kn through the output filter). "Prefer not to say" is
  an answer; skipped questions are not asked again. With a strong fraud pattern the warning is
  shown first and nothing is asked.
- **Deliberately not done:** no local OCR (a screenshot itself reaches the OCR provider because an
  image cannot be redacted before OCR; the transcript is then gated and redacted like typed text);
  no Google SDK; no thinking-budget tuning (model-specific field, left for live tuning).
- **Jury line:** "The model reads the message as data and fills a form. Our code checks every
  answer: it must quote the message, it can only add warnings, never remove ours, and if the
  model fails or is attacked, Ruko still works on its own deterministic patterns."

## Stage 7: Speech services

- **Built:** `providers/speech/` (`STTProvider`, `TTSProvider`, `SpeechProvider`, `SarvamProvider`
  over httpx, `FakeSpeechProvider`, `SpeechChain` fallback built from `settings.speech_providers`),
  `providers/speech/audio.py` (base64, size, magic-byte format check, WAV duration),
  `language/speak.py` (template references -> filtered text for TTS), `language/speech_codes.py`
  and `data/policy/speech.yaml`. Gemini and Sarvam now share `providers/http.py` (one retry loop).
- **Why:** voice is how many users will reach Ruko, but a voice provider must never become a way
  to make Ruko say something it would not write. TTS only reads templates re-rendered on the
  server and passed through the output filter; slot values must look like numbers (`₹1,50,000`,
  `12.5%`), so a client cannot slip its own words into speech.
- **Limits:** audio is decoded in memory, size-checked, and its declared format must match its
  magic bytes. WAV duration is measured exactly; other formats are bounded by the size limit and
  by Sarvam's short-audio REST limit (no audio-decoding dependency added).
- **Fallback:** providers are tried in the configured order; if none works the error is
  `SPEECH_UNAVAILABLE` and the text path keeps working. Bhashini is reserved but not built
  (no credentials). Spoken languages are data (`speech_code` in `languages.yaml`).
- **Deliberately not done:** no audio is written to disk or logged; transcripts are raw user text
  and go through the same gate and redaction as typed text; audio itself cannot be redacted
  before STT (same trade-off as screenshots).
- **Jury line:** "Ruko's voice can only read Ruko's own pre-written, filtered sentences. Even the
  numbers slotted into them are checked to be numbers."

## Stage 8: Just-in-time knowledge cards

- **Built:** `data/cards/catalog.yaml` (10 cards with conditions, priority, safety-critical flag,
  slot builder and cited facts), `cards/catalog.py` (loads the catalog, resolves every fact
  reference to its value + source + `as_of` + verification status), `cards/select.py`
  (deterministic selection and rendering), card and base-rate templates in en/hi/kn, and two new
  cited facts in `regulatory.yaml` (derivative losses can exceed margin; advisers may not imply
  assured returns), both marked TODO_VERIFY.
- **How selection works:** a card applies when all its conditions match (reason codes, product
  class, holding intent, and computed inputs such as the leverage illustration or the base rate).
  Seen cards fade unless they are safety-critical (scam cards). Highest priority first, at most 3,
  and on the pause screen only from L2 (L1 is one line and one question).
- **Content rules:** numbers are the user's own rupees (from the engine) or cited facts; the
  leverage card says "just arithmetic, not a forecast"; the base-rate card always adds the group
  sentence and SEBI's "does not show cause and effect" caveat; the tax card shows its `as_of` date
  and is shown only for short-term holdings of listed equity / equity funds (intraday is taxed
  differently, so Ruko says nothing there rather than something wrong). Links (SEBI Check,
  recognised-intermediaries list) travel as card sources, never inside spoken text.
- **Deliberately not done:** no card names or rates a product, broker or scheme; no personal tax
  computation; no automated registration check (the card tells the user how to look it up).
- **Jury line:** "Cards are chosen by rules in a data file, not by a model. Each one cites its
  source and date, fades once you've seen it, and scam warnings never fade."

## Stage 9: Recovery path

- **Built:** `data/facts/recovery_routes.yaml` (1930, the National Cyber Crime Reporting Portal,
  the user's bank, the broker's grievance channel, SEBI SCORES, SMART ODR; each with source,
  `as_of`, unverified), `data/policy/recovery.yaml` (scenario order, steps, evidence, drafts),
  `recovery/classify.py`, `recovery/guide.py`, and the recovery texts in en/hi/kn.
- **How it works:** the user answers yes/no questions (paid? how? installed an app? registered
  broker? unauthorised trade? cannot withdraw?). The first true answer in a fixed order picks the
  scenario; nothing true means `no_loss_yet` (added to the Stage 1 enum, so Ruko never pretends
  money moved). Urgent steps always come first: for fraud, call 1930 and the bank (only if money
  moved through a bank, UPI or card). For a registered broker, the entity first, then SCORES,
  then SMART ODR, as SCORES itself requires.
- **Drafts, not submissions:** the complaint text has blanks like `[date]` and `[transaction ID]`
  that the user fills in and sends. Ruko asks for no account numbers, OTPs or IDs, makes no
  network call, and starts every guide with "Ruko can't promise the money will come back".
- **Deliberately not done:** no bank or broker phone numbers (they differ; the user's own card or
  the official website is the safe source), no "golden hour" or timing claims we could not source.
- **Jury line:** "If you've already paid, Ruko gives you 1930 and your bank first, then the portal,
  plus a checklist and a draft complaint you send yourself, in your language, without ever
  asking for your details."

## Stage 10: Journal review (stateless)

- **Built:** `journal/review.py`, `data/policy/journal.yaml`, the `JournalReviewResponse` and
  `WeekPoint` models, and journal texts in en/hi/kn.
- **What it computes:** from entries the device sends for one request: share of decisions that
  started from a group tip or an influencer, share within the user's own rules, exit plans
  written and followed (only where the user logged the result), pauses and overrides, and
  interventions per decision week by week with a direction (`falling`, `rising`, `steady`,
  `not_enough_data`). Falling means the user needs Ruko less, which is the success metric.
- **Why this shape:** numbers + template keys only, so the client renders and speaks them; tiny
  journals still get numbers but a "too early" line; the trend compares earlier and later weeks
  with a threshold from the policy file, and needs at least 3 weeks with decisions.
- **Deliberately not done:** no score, ranking or comparison with other users; no judgement of
  gains or losses (outcomes are not analysed, so the review cannot drift into rating strategies);
  overrides are described as "both are your call"; nothing is stored.
- **Jury line:** "Our success metric is that Ruko steps in less over time. The journal review
  shows each user that trend from their own device data, and the server forgets it right away."

## Stage 11: Orchestrator and API

- **Built:** `orchestrator/executor.py` (single tool executor with the allow-list in
  `data/policy/tools.yaml`, timing, content-free trace, typed failures), `orchestrator/workflow.py`
  (analyze: adapter, language, gate, redaction, extraction, second opinion, signals, merge,
  clarify, engine, pause), `orchestrator/pause.py` (+ `data/policy/pause.yaml`),
  `orchestrator/assist.py` (speak, cards, recover, journal review, order-intent),
  `orchestrator/services.py`, `meta_info.py`, `api/v1.py`, `api/edge.py`, the reason/pause
  templates in en/hi/kn, `docs/broker_embedding_spec.md`, integration tests and 12 golden scenarios.
- **The agent, honestly:** a constrained, tool-using orchestrator. It chooses which tools run
  (OCR only for screenshots, STT only for voice, questions instead of a decision when the amount
  is missing) but never decides the level. Every tool goes through one executor that refuses
  anything off the allow-list; no listed tool sends messages, fetches links or moves money.
- **The pause by level:** L0 is a quiet headline; L1 is one reason and one question; L2/L3 show
  the user's numbers, their own rules, every reason with its certainty label, one question
  chosen by the top reason's category, and up to 3 cards. "Is this a scam?" adds the fixed
  "Ruko can't vouch" line. Every string has a `speak` reference for `/v1/speak`.
- **Edge:** JSON-only bodies with a size cap, a per-minute rate limit keyed by a salted hash,
  CORS off by default, locale must be enabled. Responses never echo message text (evidence is
  stripped from clarify events; a sentinel test checks responses and logs).
- **Contract change:** `OrderIntentRequest.exit_plan_set` (optional), so a broker can say a
  stop-loss is attached; otherwise every F&O order would get `NO_EXIT_PLAN`.
- **Jury line:** "One request goes through about ten small, named steps; the response lists them
  with timings so anyone can see exactly what ran, and none of them can message, browse or pay."

## Stage 12 (v1 plan): Evaluation harness, first run

- **Built:** `eval/datasets/messages.yaml` (153 synthetic / public-pattern items) and the first
  `eval/run_eval.py`. Honest result: signals precise (98.7%) but recall 83.5%, 0/40 false positives,
  and 6 advice/prediction phrasings plus 1 pasted password slipped past the deterministic gate.
- **Why it mattered:** it exposed a guardrail gap before any jury did. Nothing unsafe was output
  (all text is templated), but a refusal became a clarifying question.

---

# v2 realignment (CLAUDE.md and BUILD_PLAN.md rewritten by the owner on 2026-10-03)

## v2 Stage 1/4: two dimensions and the level rules

- **Built:** `ReasonCode` renamed/added (`EMERGENCY_FUNDS`, `PLAN_INCOMPLETE`, `UNPLANNED_DECISION`),
  severity tiers low/medium/high, `Dimension`, `DecisionStage`, `Action`, `DecisionPlan` (presence
  flags only; the words stay on the device), `ExposureNumbers` (`engine/exposure.py`, never "loss
  capacity"), `engine/content.py`, and a rule table in YAML (`level_rules`) evaluated generically.
- **How:** each rule says "when these conditions hold, the level is at least X"; the level is the
  maximum, so adding a reason never lowers it. Content-only and behaviour-only rules also give a
  level per dimension, returned as `dimension_levels`, with `content_codes`, `behavioural_codes`
  and `matched_rules`, so the two dimensions are never collapsed into one opaque score.
- **Deliberately:** low signals never escalate alone; one medium signal alone is a nudge; any high
  signal or protected-goal money is a strong pause; plans are expected only for derivatives and
  crypto (otherwise every ordinary decision would be nudged). Choices with alternatives:
  `docs/open_questions.md`.
- **Jury line:** "Ruko keeps two separate questions apart: what is this message doing, and what does
  this mean for you. You can see both answers and every rule that fired."

## v2 Stage 2: assertion-level output validator

- **Built:** `data/policy/output_policy.yaml`, `guardrails/output_validator.py`; every template now
  declares a `response_type`; the renderer validates per type; every `/v1` text response is checked
  once more as a whole (`ensure_safe`, `OUTPUT_BLOCKED` on failure).
- **How:** directives, predictions, named brokers and verdicts ("this is a scam") are forbidden
  everywhere. Claim words (guaranteed, assured, safe, legit) may only be *reported*: allowed in
  signal reports, cards, glossary and recovery text, and only inside a reporting frame in the same
  sentence ("the message contains a guaranteed-return claim", "SEBI's rules do not allow ...").
- **Tests:** always-forbidden and Ruko-asserting forms are blocked in every type and language;
  legitimate reporting sentences have zero false blocks.
- **Jury line:** "Ruko can say 'this message contains a guaranteed-return claim'. It can never say
  'this is guaranteed' or 'this app is safe'. The check is on what Ruko asserts, not on words."

## v2 Stage 5: decision stages

- **Built:** `data/stages/{en,hi,kn}.yaml`, `understanding/stage.py`, `docs/decision_stages.md`.
  Deterministic patterns first (every language on every input); tie-breaks in code; the LLM may only
  fill an `unknown` stage. Already-acted reports also pre-fill recovery answers (yes/no facts and the
  payment method only).
- **Why:** not every message is a decision. "What is an IPO?" gets a glossary entry, "is this
  normal?" a content report without a verdict, "I already paid" the recovery path with no
  "you should have paused", and only real decisions reach the engine.
- **Jury line:** "Ruko first asks itself what the person is trying to do, so it never lectures
  someone who only wanted a definition, and never pauses someone who already lost money."

## v2 Stage 6: LLM as a helper, via the official SDK

- **Built:** `GeminiProvider` now uses the Google Gen AI SDK (`google-genai`, pre-approved) with our
  own retry/backoff and typed errors; automatic function calling is disabled (the model has no
  tools); the SDK's logger is quietened. The extraction schema adds `stage` and `action`; prompt
  `extract-v2`. Merge precedence: deterministic results win; the LLM fills unknowns and adds signals
  one certainty step lower unless the lexicon corroborates.
- **Live check:** the SDK path authenticates and reaches Gemini; the free-tier quota (HTTP 429)
  prevented a full live run.

## v2 Stage 8: cards, glossary, fact visibility

- **Built:** `data/glossary/catalog.yaml` + `cards/glossary.py` (8 curated terms in en/hi/kn, with an
  official pointer for unknown terms; no LLM-written explanations); `action_in` card condition, so
  the tax card appears only when selling; `show_unverified_facts` (true in dev, false in prod): cards
  stating unverified facts, unverified recovery routes and glossary pointers are left out in
  production. The 1930 number moved from template text into a slot filled from the routes file.
- **Jury line:** "In production, a fact a human has not checked is simply not shown."

## v2 Stage 10: journal impact metrics

- **Built:** journal entries now record stage, override reasons, pause completion, comprehension,
  plan parts and own rules/plans counts; `journal/review.py` returns the `docs/impact_metrics.md`
  metrics (completion, comprehension, reconsideration, overrides with/without reason, plans
  set/followed, unsolicited share, rule articulation).
- **Deliberately:** a falling intervention count is shown as data, never as success on its own, and
  outcomes (gain/loss) are not analysed.

## v2 Stage 11: routing by stage, 16 golden scenarios

- **Built:** the analyze workflow routes learn → glossary, evaluate_content → content report,
  already_acted → recovery, unknown → one stage question, consider/about_to_act → clarify → engine →
  pause (urgent headline for about_to_act). The API returns six response kinds; `meta` carries the
  stage and who decided it; the broker API takes `plan_matched`.
- **Tests:** the 16 golden scenarios of the v2 plan pass end to end through HTTP with fakes.

## v2 Stage 12: evaluation with a held-out split

- **Built:** `eval/datasets/heldout.yaml` (76 items incl. learn, already-acted and is-this-real
  questions, written before any fix), stage/path/scenario/term accuracy, quiet-on-ordinary and
  over-intervention, false refusals and false blocks, LLM-off (LLM-on documented as not run).
- **Honest result:** the clean held-out baseline (`docs/eval_report_heldout_baseline.md`) refused only
  6/16 advice/secret inputs and missed 43% of content signals. Patterns were then generalised (with
  new regression sentences, not copies); the current held-out numbers are labelled contaminated.
- **Jury line:** "We kept our first, unflattering held-out result on record, because a guardrail that
  only works on the test set is not a guardrail."

## v2 Stage 0.5: share-target spike

- **Built:** `spike/share_target/` (manifest with `share_target`, empty service worker, one page that
  shows the shared text and can call `/health` and `/v1/analyze`, placeholder icons) and a device test
  checklist. It serves locally; the Android test is the owner's.

## v2 Stage 13: hardening

- **Built:** security/privacy tests (network code only in three provider modules, no key-like strings
  in the repo, every log call uses allow-listed fields and a constant event name, no `print`, error
  responses never echo input, production hides unverified facts), `docs/data_sources.md` with a sync
  test, `docs/production_path.md`, README with third-party disclosure and limitations. `pip check`
  clean. Deployment is a hard gate: host options are listed in `STATUS.md`.

## Phase 2 Stage P0: contract fixes

- **Built:** each signal now carries its certainty label and its explanation as separate fields
  (`certainty_label`, `reason_text`) next to the old combined `text`; pause signals now carry their
  severity; the pause response carries a small `event` summary (stage, action, product class,
  source type). One shared function renders a signal for both the pause and the content report.
- **Why:** the frontend had to cut "Likely: " off English text to show a badge, which breaks in
  Hindi and Kannada, and its journal had to guess the product class from an earlier question.
- **Does not:** remove or change any existing field (old clients keep working), or put message text
  in the event summary.
- **Jury line:** "The app never parses Ruko's sentences; every piece it shows arrives as its own
  typed field, in the user's language."

## Phase 2 Stage P1: calculation tools and the `calculate` stage

- **Built:** five pure calculators in `src/ruko/tools/finance.py` (SIP, goal, inflation,
  consequence of a fall, trading costs; integer rupees, documented formulas, no I/O), a parser
  that reads numbers from the user's own words in English, Hindi and Kannada
  (`tools/params.py`, unit words in `data/stages/*.yaml`), a new stage `calculate`, and a
  `calculation` response with `assumptions[]`, two or more `scenarios[]` and
  `is_illustration: true`. Missing numbers become clarify questions.
- **Why:** "What will my SIP look like?" used to get a generic question. Arithmetic is useful and
  safe as long as it is plainly arithmetic: the user's numbers, labelled example rates, several
  scenarios side by side, so no single figure reads as a forecast.
- **Does not:** predict, suggest an expected return, pick a product, or let the LLM produce a
  number. The LLM may only name which calculator; "Which fund gives the best return?" is still
  refused as advice and "What will Nifty be next year?" as a prediction. The tax calculator is
  off, and statutory charges stay unused until verified.
- **Enforced in code:** a `calculation` response type with its own forbidden patterns ("you will
  get", "expected return", Hindi "मिलेगा", Kannada "ಸಿಗುತ್ತದೆ") checked per template and on the
  whole response; property tests (more months never lowers a SIP; a bigger fall never leaves
  more money).
- **Jury line:** "Ruko will do the maths for you, but it shows the maths, not a promise: your
  numbers, at least two assumed rates, and the sentence 'this is arithmetic, not a prediction'."
