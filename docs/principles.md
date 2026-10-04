# Product principles and guardrails

These are the rules Ruko is built on. Every one of them is enforced in code or in tested data
files, not only written down here. If you want to know *why* the app behaves the way it does,
start here.

## The idea in one paragraph

Financial tips reach people through channels they already trust: Telegram groups, WhatsApp
forwards, YouTube, friends. Two very different harms start from that same forwarded message.
Some people lose money in the real market by acting on impulse (F&O, intraday, IPO hype, borrowed
money). Others are pulled into a fake "market" and pay a stranger over UPI. Ruko sits in the
short moment between *"I want to act"* and *"I acted"*. It shows what this decision means for
the person's **own money, own rules and own plan**, in their language. Then it steps back. If
something has already gone wrong, it points them to the right official help.

## What Ruko is not

- Not an investment adviser, a tip rater or a trading tool.
- Not a chatbot that answers "should I buy X?".
- Not a course or a content library. Learning appears where a decision needs it, and is
  always there if someone wants to browse.
- Not a product that holds, moves or locks money.

## The two harm flows

| Flow | Path | Where Ruko helps |
|---|---|---|
| Real market, harmful behaviour | Tip → broker app → F&O / intraday / IPO | A pause before acting, the person's exposure in rupees, their own rules, a decision plan, and an API a broker could call before an order |
| Fake market, fraud | Group → fake app or site → UPI to an individual | Message signals, payment-destination checks, and an "I already paid" recovery path |

Both flows start with a message. Sharing, pasting, speaking or sending a screenshot all lead
into the same journey.

## Decision stages: not every message is a decision

Every input is first sorted into a stage, and the stage decides what happens next.

| Stage | Example | What Ruko does |
|---|---|---|
| `learn` | "What is an IPO?" | A short, curated explanation. No pause. |
| `evaluate_content` | "Is this message normal?" | The signals in the message, each with how sure we are. No verdict. |
| `consider_action` | "Thinking of putting ₹20k into this" | The full check; a pause only if something is triggered |
| `about_to_act` | "Paying this UPI ID now" | The same, shown more urgently |
| `already_acted` | "I already paid and they want a fee to withdraw" | Recovery steps. No "you should have paused". |
| `calculate` | "What will my SIP of 5000 look like?" | Arithmetic shown under stated assumptions, never a forecast |
| `unknown` | unclear | One clarifying question |

Sorting is deterministic first (patterns per language). The language model only helps when the
patterns cannot decide. When it is unclear whether someone is about to act or has already acted,
Ruko asks.

## Two separate questions, never one opaque score

1. **What is the message doing?** Content signals such as guaranteed-return claims, urgency,
   impersonation or a payment to a personal UPI ID. Each one has a severity (`low`, `medium`,
   `high`) and a certainty (`possible`, `likely`, `unclear`).
2. **What does this mean for this person?** Behavioural context: their own rules, protected
   goals, borrowed or emergency money, a first-time product, whether they wrote a plan.

The intervention level (L0 quiet → L3 strong pause) is a documented, deterministic function of
both. A single low-severity signal never causes an alarm. High-severity fraud signals, or
several medium ones together, reach the strongest level. See `docs/intervention_policy.md`.

## Design principles

1. **The decision is always the person's.** Ruko never blocks. Every pause has a "continue
   anyway", and the choice is recorded in the person's own journal.
2. **Quiet by default.** Ordinary decisions pass with one line. Friction appears only when
   the person's own rules, a new risk or clear message signals call for it.
3. **Never argue with the tip.** People trust their tipster more than a new app. Ruko never
   says a tip, stock, scheme or person is good, bad, safe or legit. It moves attention to the
   person's own money, rules and plan.
4. **Small cognitive load.** At most three short explanation items, one reflection question,
   and numbers in the person's own rupees.
5. **Teach what this decision needs.** Lessons are chosen for the decision at hand and fade
   once read. A full Learn list is always available for anyone who wants it.
6. **Deterministic code decides; the language model only understands.** The stage, level,
   reasons, every number and every sentence the person reads come from tested code and
   human-written templates. The model only turns messy input into structured fields.
7. **Works without the model.** If the model is down, slow or removed, Ruko still runs on its
   own patterns, with lower coverage and the same safety.
8. **Uncertainty is always stated.** Every signal carries a certainty label. There are no
   yes/no verdicts.
9. **Privacy by design.** The profile and journal live on the phone. The server keeps nothing,
   removes personal details before any external call, and never logs message content.
10. **Bharat first.** English, Hindi and Kannada from day one. Adding a language is a data task,
    not a code change. Voice in and out.
11. **Public good.** No monetisation, no upsell, no broker or product promotion.
12. **Provider-agnostic.** Every external AI service sits behind an interface. Gemini and Sarvam
    are prototype choices, not architecture. See `docs/production_path.md`.

## Calculators and Learn

- **Calculators show arithmetic, not predictions.** The numbers come from tested pure functions
  using values the person gave or clearly labelled example rates. At least two scenarios always
  appear side by side, every result lists its assumptions, and every result is marked as an
  illustration.
- **Asking for numbers is not asking for advice.** "What will my SIP look like?" goes to a
  calculator. "Which fund should I buy?" is refused.
- **Learn is curated.** Ruko picks and orders short, reviewed lessons and fills in the
  person's own numbers. It never writes lesson text with a model. Every lesson and every
  glossary word lives in a data file with its sources.

## Guardrails (enforced in code)

Ruko must never produce, in any language:

- stock tips, buy / sell / hold signals, or a recommendation about any security, scheme, fund,
  platform or broker
- price predictions or predictions of investment outcomes
- trading strategies or algorithms
- promotion of any instrument, broker, platform or scheme
- monetisation funnels (commissions, margin nudges, paid upsells)
- any statement *by Ruko* that a tip, scheme, app or person is safe, legit, genuine or guaranteed

And Ruko must never:

- collect OTPs, passwords, PINs, card or account numbers, SMS inboxes or contacts
- open links from a message (links are analysed as text only)
- send a message on the person's behalf (it writes drafts; the person sends them)
- decide how much someone "can afford to lose" (it shows exposure against the person's own
  figures and rules, and never sets a "safe" amount)

How this is enforced, layer by layer:

1. **Input gate.** Advice, prediction, product-evaluation, broker and role-play requests, and
   pasted secrets, are refused with a typed reason. Patterns run first. A model may add a
   refusal but can never remove one.
2. **Structured output.** Every response is a typed object rendered from templates. Each
   template declares what kind of text it is (`signal_report`, `refusal`, `lesson`, and so on).
3. **Assertion-level validator.** It checks what Ruko *claims*, not just which words appear.
   "This message contains a guaranteed-return claim" is allowed. "This is guaranteed" and
   "this app is safe" are blocked. It runs on every string and once more on the whole response.
4. **A guardrail test suite** of over 400 multilingual adversarial cases, which must pass at 100%.

## Facts and sources

Ruko shows statistics, rules, helpline numbers and portal names. A wrong fact is a safety
failure, so:

- Every fact lives in a data file (`data/facts/`) with its value, source URL, source title,
  date and a `verified_by_human` flag.
- Nothing is invented. A fact without a primary source is marked `TODO_VERIFY` and is not shown.
- Primary sources come first: sebi.gov.in, nsdl.co.in, cybercrime.gov.in, npci.org.in and
  official provider documentation.
- Statistics are shown as **group statistics** from the cited study, never as a prediction for
  this person. SEBI's note that the relationships are not causal is kept.
- In production (`RUKO_ENVIRONMENT=prod`), anything not verified by a human is hidden.

The full list with verification status is in `docs/data_sources.md`.
