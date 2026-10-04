# Design decisions

Why each part of Ruko is built the way it is, and what it deliberately does not do. The
sections follow a message through the system. Each ends with the one-line version we would
give if asked.

The product rules these decisions follow are in [principles.md](principles.md). The places
where we had to choose a default without a rule to follow are in
[open_questions.md](open_questions.md).

---

## 1. Foundation: a server that cannot leak what you typed

- **What:** a FastAPI service with typed settings, a request ID on every call, JSON logs and
  one error shape, `{error: {code, message_key, retryable}}`.
- **Why:** privacy and predictability first. Log lines are built only from an allow-list of
  field names. Message text cannot reach a log even by mistake. The middleware logs the route
  template (`/v1/analyze`), never the raw path or query.
- **Deliberately not done:**
  - FastAPI's default validation error, which echoes the submitted input, is replaced by one
    that returns only field locations.
  - Exception messages are never logged, only their type.
  - Library access logs that print full URLs are silenced.
- **Secrets:** API keys are `SecretStr` and never print.

> *"The server cannot log what a user typed. The logger only accepts allow-listed fields, and a
> test sends a sentinel string in the body, query and path and proves it never appears."*

## 2. Contracts that make the unsafe thing unrepresentable

- **What:** every request and response is a Pydantic model (`src/ruko/models/`). All models
  reject unknown fields, so a client cannot slip an `otp` or `account_number` field in.
- **Limits built into the schema:**
  - `override_allowed` is the literal `True`.
  - `Certainty` has no "certain" value.
  - The pause carries at most three cards.
  - The broker order-intent request has no instrument field and no user ID.
- **Money:** integer rupees everywhere. Ratios such as months of expenses and share of savings
  are shown as ranges, because profiles are sent as bands by default.
- **Speech by reference:** `/v1/speak` accepts only template keys plus number-like slot values,
  re-rendered on the server. Speech can therefore only read Ruko's own sentences.
- **What Ruko cannot know:** the observability matrix ([observability_matrix.md](observability_matrix.md))
  lists signals that would need broker or bank data and marks them unavailable, so Ruko never
  claims to detect them.

> *"There is no field for a stock name in the broker API, no 'certain' label, and 'continue
> anyway' is a constant."*

## 3. Language: three languages as data, and redaction before anything leaves

- **What:** language detection (script counting plus romanised marker words), redaction,
  Indian number formatting (`1,50,00,000`, amounts in words in en / hi / kn) and a template
  linter.
- **Adding a language is a data task.** It takes a script range and marker words in
  `data/language/languages.yaml`, a templates file and a numbers file. No code changes.
- **Redaction keeps structure, not identity.**
  - A UPI ID becomes `[UPI_USER]@oksbi`, and a phone-number UPI ID becomes `[UPI_PHONE]@ybl`.
  - The fraud checks can still see *what kind* of payee it is, but not who.
  - Amounts after ₹/Rs are never redacted.
- **Tested with properties.** Redaction never leaks generated phone numbers, UPI IDs, emails or
  long numbers. Digit grouping is correct for any integer up to 10^15.

> *"Before any text leaves our server, phone numbers, UPI IDs and account numbers are replaced
> locally, and property tests over thousands of generated values prove it."*

## 4. Guardrails: refuse the question, analyse the tip

- **Input gate** (`guardrails/intent_gate.py`, `data/policy/guardrails.yaml`):
  - It refuses advice, prediction, product-evaluation, broker and role-play requests.
  - Every language's patterns run on every input, so code-mixed text is covered.
  - A second, "de-obfuscated" pass undoes leetspeak, s.p.a.c.e.d letters and look-alike
    characters.
  - A language model may *add* a refusal but never remove one.
- **Tips are not refused; questions are.** The advice patterns are question-shaped ("should I
  buy", "will it go up?"). A forwarded "BUY NOW" tip is exactly what Ruko must analyse.
  Injection text inside a tip ("ignore your rules…") is flagged and treated as data. Since every
  output is a template, there is nothing for it to steer.
- **"Is this a scam?" gets analysis, not a verdict,** plus a fixed line: "Ruko can't vouch for
  any tip, app or person".
- **Sensitive data:**
  - OTPs, PINs, CVVs, passwords and Luhn-valid card numbers are refused with a warning.
  - Account numbers are refused only in first person ("my account number"). A payee's account
    inside a scam message is a fraud signal, not the user's secret.
- **Output validator** (`guardrails/output_validator.py`, `data/policy/output_policy.yaml`):
  - Every template declares a response type, and the validator checks what Ruko *asserts*.
  - Directives, predictions, named brokers and verdicts are forbidden everywhere.
  - Claim words (guaranteed, safe, legit) may only appear inside a reporting frame in the same
    sentence: "the message contains a guaranteed-return claim".
  - Calculations and lessons have extra rules, such as no "you will get" and no "expected
    return".
  - It runs on every string and once more on the whole response.

> *"Ruko can say 'this message contains a guaranteed-return claim'. It can never say 'this is
> guaranteed' or 'this app is safe'. The check is on what Ruko asserts, not on words."*

## 5. Decision stages: not every message is a decision

- **What:** `understanding/stage.py` and the patterns in `data/stages/{en,hi,kn}.yaml`.
  Deterministic patterns come first, tie-breaks are in code, and the model may only fill an
  `unknown` stage.
- **Why:**
  - "What is an IPO?" gets an explanation.
  - "Is this normal?" gets a content report without a verdict.
  - "I already paid" goes to recovery, with no "you should have paused".
  - "What will my SIP look like?" goes to a calculator.
  - Only real decisions reach the engine.
- **Ambiguity is asked about, not guessed.** "I paid 500 yesterday, should I add more?" mixes
  stages, so Ruko asks one question.

> *"Ruko first works out what the person is trying to do. It never lectures someone who only
> wanted a definition, and never pauses someone who already lost money."*

## 6. Signals: fraud patterns found without the model

- **What:** lexicons in three languages, including romanised variants
  (`data/lexicon/`), link checks (`understanding/links.py`) and payment checks
  (`understanding/payments.py`).
- **Certainty is conservative.** One weak pattern is `possible`. A strong pattern, or two
  different weak ones, is `likely`.
- **Links are strings, never fetched.** Ruko checks for:
  - shorteners, chat invites and APK links
  - raw IP hosts, `http://` and punycode
  - look-alikes of regulator and market domains (`sebl`, brand + "kyc")

  A test checks that these modules import no network code.
- **Payments:**
  - A UPI ID that is a phone number points to an individual (`likely`).
  - Bank details or a QR code count only when the message asks for payment.
  - SEBI's `@valid` UPI handle pattern is noted but never trusted as proof. Ruko points to
    SEBI's own check instead.
- **Quotes:** each signal shows the words it rests on (`understanding/quotes.py`):
  - The quote is a plain substring of the already-redacted text, at most 140 characters.
  - It is never logged and never spoken.
  - People trust a signal they can see in their own message.
- **Roles:** with three or more signals, they are grouped by what the message is doing to you:
  pushing you to act, making claims, where it comes from, or about you
  (`data/policy/signal_roles.yaml`). This is a heading, never a verdict, and it never changes a
  level.
- **No false alarms on ordinary messages.** SIP reminders, contract notes, dividends and
  allotment notices produce zero signals, and tests hold that.

> *"'Pay 18% GST to withdraw your profits' is caught by a deterministic pattern in English,
> Hindi or Kannada, and we never even open the link in the message."*

## 7. The language model: a helper that fills a form

- **What:** `providers/llm/` (an interface, a Gemini provider on the official `google-genai`
  SDK and an offline fake) and `understanding/extract.py` with the versioned prompt in
  `data/prompts/extraction.yaml`.
- **What it may do:**
  - It reads *redacted* text between fixed markers and returns JSON that Pydantic validates.
  - It may propose a short list of message-pattern codes, each with an exact quote as
    evidence. A quote that isn't in the text drops the signal.
  - It has no tools (automatic function calling is off).
- **What it may never do:** output an amount or funding source (the schema has no such
  field), claim a payee is a broker, raise the sensitive-data refusal, or touch the level.
- **Disagreement rule:**
  - The person's answers win.
  - Deterministic findings are never removed or weakened.
  - Anything only the model saw is kept one certainty step lower.
  - A conflict becomes "unknown", and Ruko asks.
- **Works without it.**
  - Invalid JSON is retried once.
  - After that, or on any provider failure, Ruko runs on its own patterns.
  - When the main model is out of quota or unavailable, it switches to a fallback model for
    ten minutes.
- **Screenshots** go to the model for reading, because an image cannot be redacted first. The
  text read from them is then gated and redacted like typed text.

> *"The model reads the message as data and fills a form. Our code checks every answer. It must
> quote the message, it can only add warnings, never remove ours, and if it fails or is
> attacked, Ruko still works."*

## 8. The safety engine: two dimensions, one documented function

- **What:** `engine/` with every threshold in `data/policy/intervention.yaml`.
- **Two separate questions.** Content signals ("what is this message doing?") and behavioural
  context ("what does it mean for you?") are kept apart. The response returns a level per
  dimension and the list of rules that fired, so they are never merged into one opaque score.
- **How a level is decided:**
  - Each rule says "when these conditions hold, the level is at least X".
  - The level is the maximum, so adding a reason can never lower it, and a property test
    holds that.
  - Low signals never escalate alone, and one medium signal alone is a nudge.
  - Any high signal, or protected-goal or emergency money, is a strong pause.
- **Two softeners touch only the mildest level:**
  - A novelty-only nudge fades after a streak of rule-following decisions.
  - A weekly attention budget can silence only all-low nudges.
- **Honest numbers:**
  - Bands give a range plus a typical value ("about 2 months, 1.5 to 3").
  - A rule breach is `likely` only if it holds across the whole band.
  - The leverage illustration is plain multiplication on the person's own amount, labelled
    as an illustration.
- **Late at night:** the phone sends one yes/no from its own clock (23:00 to 05:00), never the
  time. It never raises a level alone. It counts only beside a medium message signal.
- **Docs cannot drift.** Tests regenerate the policy tables from the YAML and compare them
  with [intervention_policy.md](intervention_policy.md) and [reason_codes.md](reason_codes.md).

> *"The level is a pure function of your own numbers, your own rules and the patterns in the
> message, with every threshold in one YAML file. We property-test that more risk never means
> less friction."*

## 9. The pause: proportional, personal, never a lock

- **By level:**
  - **L0:** one quiet line.
  - **L1:** one reason and one question.
  - **L2 and L3:** the person's money (share of savings, months of expenses, what a fall would
    do), their own rules, every reason with its certainty, one reflection question chosen by
    the top reason, and up to three cards or lessons.
  - **L3:** also starts a cooling-off timer of the person's own length. It can be skipped at
    any moment.
- **Asks only what it cannot read.**
  - Amount, funding source and product are asked in one short form.
  - Values the message mentions are offered as taps, never filled in silently.
  - Counts of people ("48,213 members") are never offered as amounts.
  - With a strong fraud pattern, the warning comes first and the questions come after.
- **Pace:** three skipped reflections on an L1 or L2 pause go straight to the decision.
  L3 is never shortened.
- **"Continue anyway" is always there.** The choice, and any reason given, goes to the person's
  own journal on their phone.

> *"It asks only what it can't read from your message, shows your own words and your own
> rupees, and gets out of the way when you're moving fast, unless the signals are strong."*

## 10. Explanations: cards, lessons and a word layer, all curated

- **Cards** (`data/cards/catalog.yaml`):
  - They are chosen by rules: reason codes, product class, action.
  - Each one cites its source and date.
  - Seen cards fade, except scam cards. There are at most three per pause.
  - The base-rate card always says it is a group statistic and keeps SEBI's "does not show
    cause and effect" caveat.
- **Lessons** (`data/learn/lessons.yaml`):
  - Fifteen short lessons (60–120 words) in three languages, filled with the person's own
    rupees.
  - Cards and lessons share one budget: at most three items, safety-critical first.
  - A few lessons give general habit guidance and no facts. They are labelled "general guidance
    from Ruko, not from an official source" and contain no numbers.
- **The Learn list** (`/v1/learn`) is always available, with no trigger needed. It is ordered
  per person: what they are looking at, then what they told Ruko (a recent loss, frequent
  trading, late night), then experience, then a default path. A quiet result, a glossary
  answer, a calculation and Home each offer the one lesson on the same subject.
- **The word layer** (`learn/terms.py`):
  - The backend finds glossary words in Ruko's own rendered text and returns them.
  - The app turns each into a button, and a tap opens a one- or two-line explanation.
  - It works the same in the pause, signals, cards, calculator and lessons.
- **No model writes any of this.** Ruko is dynamic in what it *picks*, not in what it *says*.

> *"Learn is ordered for you from what you've told Ruko, and every financial word in Ruko's
> text explains itself in one tap. Nothing in it is written by a model."*

## 11. Calculators: arithmetic, never a forecast

- **What:** pure functions in `tools/finance.py` for SIP, goal, inflation, the effect of a fall
  and trading costs. They use integer rupees, have documented formulas and do no I/O.
  `tools/params.py` reads numbers from the person's own words in three languages.
- **Rules:**
  - At least two scenarios side by side, at the person's own rate or at example rates labelled
    "for illustration, not expectations".
  - Every result lists its assumptions and is marked as an illustration.
  - Missing numbers become questions.
- **Boundaries:**
  - "Which fund gives the best return?" is still refused as advice.
  - "What will Nifty be next year?" is refused as a prediction.
  - The model may only name which calculator to use. It never produces a number.
  - The tax calculator stays off until its rules are verified.
- **Property tests:** more months never lowers a SIP, and a bigger fall never leaves more money.

> *"Ruko will do the maths, but it shows the maths, not a promise: your numbers, at least two
> assumed rates, and the words 'an illustration, not a prediction'."*

## 12. Recovery: urgent steps first, no promises

- **What:** `recovery/`, the ordered routes in `data/facts/recovery_routes.yaml` (1930, the
  National Cyber Crime Reporting Portal, the person's bank, the broker's grievance channel,
  SEBI SCORES, SMART ODR) and the scenarios in `data/policy/recovery.yaml`.
- **How:**
  - A few yes/no questions pick the scenario.
  - For fraud: call 1930 and the bank first.
  - For a registered broker: the broker first, then SCORES, then SMART ODR, the order SCORES
    itself requires.
- **Drafts, not submissions.** The complaint has blanks like `[transaction ID]` that the person
  fills in and sends. Ruko asks for no account numbers, OTPs or IDs.
- **No promises.** Every guide starts with "Ruko can't promise the money will come back". A
  test checks recovery text in three languages for refund or reversal promises.
- **Deliberately not done:** no bank or broker phone numbers (they differ, and the official
  website or card is the safe source), and no timing claims we could not source.

> *"If you've already paid, Ruko gives you 1930 and your bank first, then the portal, plus a
> checklist and a complaint draft you send yourself, without asking for your details."*

## 13. Journal and impact: measured on the person's own phone

- **What:** the journal stays on the phone. `/v1/journal/review` computes the person's own
  patterns for one request and forgets them. It reports:
  - how many decisions started from a tip
  - how many stayed within their own rules
  - plans written and followed
  - pauses read through, reconsiderations and overrides, with or without a reason
  - interventions per week with a trend
- **Deliberately not done:**
  - no score, ranking or comparison with others
  - no analysis of gains or losses, so the review cannot drift into rating strategies
- **Fewer pauses is not automatically success.** It is shown as data, next to whether the
  person understood the pause and what they did next. See
  [impact_metrics.md](impact_metrics.md) and [pilot_protocol.md](pilot_protocol.md).
- **Anonymised summary:** a downloadable file of counts only. A test plants secrets and checks
  they never appear in it.

> *"We measure whether people understood the pause and what they did next, and the summary file
> cannot contain what you typed."*

## 14. Orchestration and the broker API

- **One executor.** Every step of a request (OCR, speech, extraction, engine, cards,
  calculators, recovery) runs through one tool executor with an allow-list
  (`data/policy/tools.yaml`). None of the listed tools can send a message, open a link or move
  money. The response lists the steps with timings.
- **Edge:**
  - JSON-only bodies with a size cap
  - a per-minute rate limit keyed by a salted hash
  - CORS off by default
  - a Content-Security-Policy on the app page
- **Broker embedding** ([broker_embedding_spec.md](broker_embedding_spec.md)):
  - The broker sends the product class, an amount band, leverage and borrowed flags, and the
    device profile. It never sends a stock or a user ID.
  - Ruko returns a level and reason codes, and the broker words them.
  - The app includes a plainly fictional broker screen that shows this.

> *"A broker could call Ruko before an order without telling it which stock or who the user is."*

## 15. The app: installable, shareable, light

- **What:** a React + TypeScript PWA in `frontend/`. It renders what the backend decided, one
  component per response kind, and never computes a level or a number itself.
- **Share from anywhere.**
  - The app is an Android share target for text, links and photos.
  - When the service worker can't take a shared photo (for example on the first launch after
    install), the server hands it back inside the page as an inert data block. Nothing is
    stored.
- **Offline:** rules, journal and the recovery checklist work offline. Analysis says plainly
  that it needs a connection.
- **Small:** the entry bundle is under 100 KB gzip. Calculator, Learn, charts and the broker demo
  load on demand. No web fonts.
- **Accessible:** large-text mode, 44 px tap targets, colour never the only cue, voice in and
  out (Ruko's voice through Sarvam, else the phone's own voice, and it says which).
- **One command checks it all.** `scripts/smoke_test.py` starts the real product, walks every
  journey and loads the built page in a headless browser.

## 16. Evaluation: we kept the unflattering numbers

- **Three labelled splits** in `eval/datasets/`:
  - **Development:** 153 items, used to find and fix gaps.
  - **Held-out:** 76 items written before any fix.
  - **Calculator and lessons:** 29 items written from the design before the first run.
- **The first held-out run is frozen** in [eval_report_heldout_baseline.md](eval_report_heldout_baseline.md):
  the deterministic gate refused only 6 of 16 unseen advice and secret phrasings, and missed 43%
  of content signals. We then generalised the patterns with new regression sentences, not
  copies. The current held-out numbers are labelled as contaminated.
- **Even at the baseline, nothing unsafe was output.** Every output is a validated template, so
  a missed refusal became a clarifying question instead.

> *"We kept our first, unflattering held-out result on record, because a guardrail that only
> works on the test set is not a guardrail."*
