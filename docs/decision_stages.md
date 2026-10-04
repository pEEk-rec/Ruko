# Decision stages

> Status: **DRAFT — awaiting user review** (v2).

Not every message is a decision. Every input is first classified into a decision stage, and
the stage decides the path (CLAUDE.md 1.2). Classification is deterministic first (patterns
per language in `data/stages/{en,hi,kn}.yaml`, run on every input, including romanized and
code-mixed text); the LLM may only fill a stage that the patterns left `unknown`.

## The seven stages

| Stage | What the user is doing | Example inputs | Path | Response `kind` |
|---|---|---|---|---|
| `learn` | Asking what something means | "What is an IPO?" · "SIP क्या होता है?" · "ನಾಮಿನಿ ಅಂದರೆ ಏನು?" · "NAV kya hota hai" | Curated glossary (`data/glossary/catalog.yaml`). No pause, no engine. Unknown terms get "not in Ruko's glossary" plus the SEBI investor-site pointer. | `glossary` |
| `evaluate_content` | Asking whether a message is real or normal | "Is this message normal?" · "क्या यह मैसेज असली है?" · "ಈ ಮೆಸೇಜ್ ನಿಜವೇ?" | Content signals with severity and certainty. No verdict, no behavioural engine; safety-critical cards; recovery pointer if message signals alone reach L3. | `content_report` |
| `consider_action` | Thinking of acting, or sharing an offer or tip | "Thinking of putting money into this IPO" · "इसमें पैसे लगाने की सोच रहा हूँ" · "ಹಾಕಬೇಕು ಅಂತಿದ್ದೇನೆ" · a forwarded tip with no note | Clarify missing amount / funding / product class, then the full engine; a pause only if triggered. | `clarify` or `pause` |
| `about_to_act` | Acting right now | "Buying 2 lots right now" · "अभी भेज रहा हूँ" · "ಈಗಲೇ ಖರೀದಿಸುತ್ತಿದ್ದೇನೆ" | As `consider_action`, with the urgent headline at L2/L3. | `clarify` or `pause` |
| `already_acted` | Reporting that money already moved or something went wrong | "I already paid…" · "can't withdraw, they want a fee" · "मैंने भेज दिए" · "ಕಳುಹಿಸಿಬಿಟ್ಟೆ" | Recovery guide; answers pre-filled from the text (yes/no facts and payment method only). No pause, no "you should have paused". | `recovery` |
| `calculate` | Asking Ruko to work out numbers (phase 2) | "What will my SIP of 5000 a month look like?" · "What happens to 40000 if this falls 25%?" · "मेरी 5000 की एसआईपी 10 साल में कितनी होगी?" · "ತಿಂಗಳಿಗೆ 5000 ಎಸ್‌ಐಪಿ 10 ವರ್ಷದಲ್ಲಿ ಎಷ್ಟಾಗುತ್ತದೆ?" | Calculator (SIP, goal, inflation, consequence of a fall, trading costs): arithmetic under stated assumptions, at least two scenarios, never a prediction. Missing numbers become questions. | `calculation` or `clarify` (fields `calculation.*`) |
| `unknown` | Unclear | "good morning" | One question: "What would you like Ruko to do with this?" with five choices. | `clarify` (field `stage`) |

The input guardrail always runs first: an advice request, a prediction request or pasted
secrets are refused before any stage is considered.

## Order of evidence

1. A stage the user chose in the app (`answers.stage`) wins.
2. Patterns. When several stages match:
   - `already_acted` together with `consider_action` or `about_to_act` is ambiguous
     ("I paid 500 yesterday, thinking of adding more") → `unknown`, so Ruko asks.
   - Otherwise the most specific path wins:
     `already_acted` > `about_to_act` > `calculate` > `consider_action` > `evaluate_content` >
     `learn`. (An explicit calculation question wins over "thinking of investing"; acting right
     now still gets the pause.)
3. No pattern:
   - a declared amount → `consider_action` (the user said they are deciding);
   - shared content that looks financial (product hints or message signals) →
     `consider_action` (Ruko's premise: a message is shared at the moment between "I want
     to act" and "I acted"), source `default`;
   - anything else → `unknown`.
4. The LLM's `stage` is used only when the deterministic result is `unknown`, and is
   recorded as `stage_source: llm` in the response metadata. For `calculate`, the LLM may also
   name the calculator (`calculator_tool`); it never supplies a number.

When the stage is `consider_action` or `about_to_act` from the user's own words or answers,
the event is always treated as a financial decision.

## Tie-break examples

| Input | Matched | Result |
|---|---|---|
| "What is margin? Is this message real?" | learn, evaluate_content | `evaluate_content` |
| "Is this real? I'm paying it now" | evaluate_content, about_to_act | `about_to_act` (the engine still reports the content signals) |
| "I sent them money, is this a scam?" | already_acted, evaluate_content | `already_acted` (help first) |
| "I paid 500 yesterday and I'm thinking of buying more" | already_acted, consider_action | `unknown` → one question |
| "I paid ₹500 yesterday, should I add more?" (plan example) | already_acted, consider_action | refused first by the input guardrail (it asks Ruko whether to invest more); without the "should I" it would be `unknown` → one question, never a fraud guide by assumption |
| "Your profit is ready. Pay 18% tax to withdraw it." (forwarded) | none (no first person) | `consider_action` via financial content → pause with the fraud signal |
| "Which fund gives the best return?" | — | refused first by the input guardrail (`ADVICE_REQUEST`): picking a product is advice, not arithmetic |
| "What will Nifty be next year?" | — | refused first (`PREDICTION_REQUEST`) |

## What stages never do

- They never route around the guardrail: refusals happen before stage classification.
- They never lower friction for a fraud pattern: a forwarded scam is still analyzed.
- The LLM can never override a stage found by the patterns (golden test 11).
