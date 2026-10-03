# Journey map

> Status: **draft, awaiting the repo owner's approval** (BUILD_PLAN Stage 1).

Ruko covers two harm flows that both start with a forwarded message:

- **Flow 1, real market, harmful behaviour:** tip → broker app → F&O / intraday / IPO.
- **Flow 2, fake market, fraud:** group → fake app or site → UPI to an individual's account.
  This flow never touches a broker.

The journey has three phases. For every step: the user's goal, the question they feel,
what Ruko observes, what Ruko does, and what Ruko must not do.

---

## BEFORE (while calm)

| Step | User's goal | Felt question | What Ruko observes | What Ruko does | Ruko must not |
|---|---|---|---|---|---|
| B1. Set own rules | Protect myself from my future impulsive self | "What limits make sense for me?" | Nothing (on-device form) | Offers rule slots: max share of savings, max per decision, no borrowed money, protected goals, cooling-off minutes. Stores them on the device. | Suggest specific numbers as "right"; recommend products; store rules on the server |
| B2. Declare context | Let Ruko speak in my rupees | "Do I have to share my salary?" | Bands (expenses, savings), optional age band, experience per product class | Explains why each field helps; bands by default; everything optional | Require exact figures; ask for income proof, PAN, account numbers |
| B3. Log a plan (optional) | Decide calmly before the market opens | "What will I do and when will I exit?" | Product class, amount range, exit rule | Saves the plan on the device; matching decisions later get low friction | Judge whether the plan is good; propose an exit level |

## DURING (a message arrives)

| Step | User's goal | Felt question | What Ruko observes | What Ruko does | Ruko must not |
|---|---|---|---|---|---|
| D1. Message arrives | Not miss out | Flow 1: "Should I jump in?" / Flow 2: "Is this my chance?" | Nothing yet; the user decides to share | Is available from the share sheet, paste, voice note or screenshot | Read chats, SMS or contacts on its own; follow the link |
| D2. Share to Ruko | Get a quick sense-check | "What does this mean for me?" | The shared text / transcript / OCR text, a link *string*, the claimed language | Detects language and script; redacts phone numbers, UPI IDs, account-like numbers and emails locally before any external call | Fetch the URL; store or log the content; process OTPs/PINs (refuses and warns instead) |
| D3. Guardrail gate | (invisible) | — | Intent of the text | If the user asks "should I buy X", "will it go up", "which broker is best", or "pretend you're my advisor", returns a fixed refusal that offers the pause instead | Answer the question, even "hypothetically" |
| D4. Understand | (invisible) | — | Product class, source type, payment destination, red-flag patterns with evidence | LLM extracts fields from redacted text as data; the lexicon finds patterns; disagreements lower certainty | Treat message text as instructions; infer the amount or funding source |
| D5. Ask what's missing | Answer quickly | "Why is it asking me this?" | Missing amount / funding source / product class | Asks at most a few tap-to-answer questions | Guess the amount; ask for sensitive data |
| D6. Decide level | (invisible) | — | Event + profile | Deterministic engine: level L0–L3, reasons, personal numbers | Use the LLM; use certainty to hide a fraud pattern |
| D7. Pause | Understand my own stakes | Flow 1: "Can I afford this going wrong?" / Flow 2: "Is something off?" | — | Shows: your numbers (months of expenses, share of savings, rupee impact of a small adverse move), your rules, signals with certainty labels, one reflection question, at most 3 short cards, in the user's language and voice | Say the tip, stock, scheme, app or person is good, bad, safe, legit or a scam; argue with the source; lecture |
| D8. User decides | Keep control | "Can I still go ahead?" | The choice: go ahead / wait / drop | Always allows "continue anyway"; at L3 suggests a cooling-off wait; records the override on the device | Block; nag; send anything on the user's behalf |

## AFTER

| Step | User's goal | Felt question | What Ruko observes | What Ruko does | Ruko must not |
|---|---|---|---|---|---|
| A1. Journal | Remember why I did it | "Was this my decision or the group's?" | On-device entry: decision, source type, exit plan, level shown, override | Saves the entry on the device | Upload the journal for storage |
| A2. Review own patterns | Get better over time | "Am I following my own rules?" | The device sends its journal for one request | Computes patterns: share of tip-driven decisions, exit plans set and followed, overrides, interventions per decision over time (should fall) | Score or rank the user; compare with others; keep the journal |
| A3. Something went wrong (Flow 2 mainly) | Get money back, stop further loss | "Who do I call, right now?" | The user's answers: paid via UPI/bank? installed an app? registered broker issue? can't withdraw? | Urgent steps first (call 1930 and the bank quickly for fraud), official portals, evidence checklist, a draft complaint the user can copy | Submit complaints for the user; promise recovery; ask for OTP/PIN/passwords |
| A3'. Registered broker issue (Flow 1) | Fix a problem with a real broker | "Where do I complain?" | Scenario answers | Broker's own grievance channel first, then SEBI SCORES, then SMART ODR | Name or rate brokers |

---

## How each flow moves through the journey

- **Flow 1 example:** a Telegram tip says "BANKNIFTY CE buy now, 300% sure". The user shares it,
  says ₹40,000 from a personal loan, and has never traded options. Ruko shows an L2 or L3
  pause: borrowed money, first time with a leveraged product, no exit plan, plus the rupee
  impact of a 2–10% adverse move on ₹40,000 and SEBI's group statistic for their age band.
  It does not comment on the tip.
- **Flow 2 example:** a WhatsApp group says "VIP platform, guaranteed 5% daily, pay ₹10,000 to
  ramesh123@okbank to activate". Ruko shows L3 with signals (guaranteed return: likely;
  payment to a personal UPI ID: likely), a card that registered brokers don't collect money
  into personal UPI IDs, and the "Already paid?" recovery entry.
