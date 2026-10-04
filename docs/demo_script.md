# Demo script (3 to 5 minutes)

Every input below was run against the real backend (LLM off, development configuration) and the
results are what you will see. Say the **bold** lines; the rest is what to tap or paste.

**Before you start (once, off stage):** `.venv/Scripts/python scripts/smoke_test.py` passes;
the app is open on a phone or a 390 px wide browser window; the language is English. First run:
pick English → **Next** → on the rules step set *Monthly expenses* ₹25,000 to ₹50,000, *Savings*
₹1,00,000 to ₹3,00,000, *At most this % of my savings* **10**, *Minutes I want to wait* **1**
(so the wait is short on stage), tick *I don't invest borrowed money* → **Next** → **Start using Ruko**.

> **Facts and production.** In the production configuration every fact a human has not verified is
> hidden (CLAUDE.md section 3). The owner has verified the group statistics, recovery routes (so 1930
> shows), regulatory facts and SEBI scam-guide pages. Still hidden in production: the **seven lessons**
> (their text is not marked verified yet), the capital-gains tax card and glossary pointers that cite
> `sebi_investor_website` (open TODO_VERIFY). For a demo that shows lessons, use the development
> configuration, or set `RUKO_SHOW_UNVERIFIED_FACTS=true` for the demo only and say so.

## 1. Quiet when nothing stands out (about 30 s)

**"Most of the time Ruko says almost nothing."**

- Home → **Think through a decision**. Type `Thinking of buying some Infosys shares`.
- Answer: amount `2000`, **My savings**, **Company shares**.
- Result: **L0**, one line, "Nothing here crosses your own rules. Ruko has noted it." and **Continue**.
  No lesson, no card, no lecture.

## 2. A real pause, in the user's own terms (about 1 minute)

**"A forwarded tip arrives. Ruko doesn't argue with it. It shows what it means for this person's own money."**

- Home → **Share something**. Paste `Guaranteed 3x return in 7 days. Join our Telegram group, act today!`
- Answer: `20000`, **My emergency money**, **A scheme, app or platform**.
- Result: **L2**, "Pause for a moment". Point at: the signals each with *Likely* or *Possible*; "Your
  context" (the ₹ amount against their own savings); one reflection question.
- Tap **Learn why this matters** → one short lesson, *Why promised returns matter* (about 30 seconds
  to read, SEBI sources, "Not yet checked by a person"). Tap **Listen** (needs the Sarvam key; without
  it the phone's own voice reads it and a line says so).
- **"Ruko can say this message contains a guaranteed-return claim. It never says the group is a scam
  or safe."** Tap **Think this through**, pick a reason, **Continue**, choose **Wait for now**.
  Journal note saved. Point out the optional one-tap "How did that pause feel?".

## 3. A stronger pause, with a wait that is never a lock (about 45 s)

- Home → **Think through a decision**. Type `Thinking of buying 1 lot of nifty options`.
- Answer: `40000`, **Borrowed (loan, credit card or from someone)**, **Futures or options (F&O)**.
- Result: **L3**, "Stop and take some time". Your own rules appear ("at most 10% of your savings",
  "no borrowed money"), a leverage card and a lesson in rupees, and a **countdown** of the 1 minute you
  set.
- **"The wait is theirs, not ours. It can be skipped."** Tap **Skip the wait**, then the continue
  button. Ruko records that the wait was skipped in the user's own journal and does not mind.

## 4. A calculation, never a prediction (about 45 s)

- Home → **Work out a number**. Type `What will my SIP of 5000 a month look like over 10 years?`
- Result: three scenarios side by side at **example rates labelled as such**, a line chart, and
  "An illustration of arithmetic, not a prediction", plus the SIP lesson with the user's ₹5,000.
- **"Ruko never says what you will earn. It shows the arithmetic under assumptions, at least two at a time."**
- Optional second input: `I put 50k in options with 5x leverage, what if it drops 25%`. Bars show the
  loss for each fall and a marker at the money put in: the 25% and 50% falls pass the marker.

## 5. If something already went wrong (about 40 s)

- Home → **I already paid**. Answer **Yes**, **UPI**, "Is a platform refusing to let you withdraw?"
  **Yes** → **Show me what to do**.
- Result: urgent steps first (1930 is a tap-to-call link), an evidence
  checklist with tick boxes kept on the phone, and a draft complaint to copy and send themselves.
- **"No promise of a refund, and nothing sent for you."**

## 6. A refusal, said plainly (about 20 s)

- Home → **Share something**. Type `Should I buy Reliance?`
- Result: "Something Ruko doesn't do", and what Ruko can do instead. **"Ruko is not an adviser."**
  Try `What will Nifty be next year?` and `Which mutual fund gives the best return?` the same way.

## 7. Embedded in a broker (about 40 s)

**"A broker could call Ruko before an order, and send it no instrument and no user ID."**

- Settings → tap the version line five times → **Fictional broker demo** (or open `/demo/broker`).
- Banner: "Demo – not a real broker". Instrument **Index option B**, amount `40000`, tick leverage and
  borrowed money → **Place order**.
- A sheet in plain words (rules, borrowed money, leverage). **Place order anyway** is always there.
  The outcome is in the user's Ruko journal.

## 8. Language, and what Ruko learned (about 30 s)

- Settings → **हिन्दी** (or **ಕನ್ನಡ**): every screen switches at once; repeat step 2 to show the pause in
  Hindi. Say: **"These translations are drafts until a native speaker reviews them."**
- Home → **My patterns**: the user's own numbers in plain words and "not a score". **"Fewer pauses is
  not automatically better."**

## If something goes wrong on stage

| Symptom | Do |
|---|---|
| "Ruko can't be reached" | Backend is down or the phone is offline; Try again. The journal and rules still work offline. |
| Listen is silent | Say "this falls back to the phone's own voice", tap Listen again. No Sarvam key means no Ruko voice. |
| No lesson appears | Production hides lessons until their text is marked verified: use development, or `RUKO_SHOW_UNVERIFIED_FACTS=true` for the demo. |
| Gemini 429 | Ignore; the lexicon path is the demo. |
