# Pilot protocol

A short, scenario-based pilot with 10 to 20 volunteers. It tests whether Ruko's **adaptive** pause
(quiet when nothing stands out, stronger when the user's own rules or the message's signals
call for it) is understood and useful, compared with a **fixed prompt** shown every time. It uses
only fictional scenarios, no real money and no personal data.

This is a small usability pilot, not a study. It cannot show that Ruko improves anyone's
investing, and the write-up must not claim that.

## 1. Questions

1. Do people read the pause through, and can they say in their own words why it appeared?
2. After a pause, do people change, delay, plan or drop the decision, or continue? (All are fine;
   Ruko never judges the choice.)
3. Do people who continue past a pause give a reason?
4. Does the adaptive pause feel more helpful, or more annoying, than a fixed prompt every time?
5. In a scam scenario, can people reach the recovery steps and use the checklist?

A falling number of pauses is **not** a success measure (`docs/impact_metrics.md`): it can also mean
the scenarios were easy.

## 2. Design

- **Who:** 10 to 20 adult volunteers (friends, family, classmates) who are not shown anyone's real
  messages. Aim for a mix of languages (English, Hindi, Kannada) and of investing experience.
- **Within-subject:** each volunteer does the same six scenarios in two arms, in a random order
  (half start with arm A, half with arm B), on their own phone or a lent one.
  - **Arm A, adaptive:** the app as built.
  - **Arm B, fixed prompt:** the facilitator reads or shows the same card before every scenario:
    *"Before you decide, take a moment. What is this decision, and what would make you stop?"*
    The volunteer then still answers the scenario using the app's result screen with the facilitator
    covering nothing; the card is simply an extra step. **There is no in-app "always prompt"
    switch yet** (see `docs/open_questions.md`, "pilot control arm"): arm B is
    delivered by the facilitator, not by Ruko.
- **Scenarios** (all fictional; the facilitator reads the text aloud or pastes it; screenshots of
  these are fine):
  1. A forwarded "guaranteed 3x in 7 days, join our group" message, with the volunteer pretending
     ₹20,000 of emergency money (expect a pause with a lesson).
  2. A first-time options trade of ₹40,000 with pretend borrowed money and the volunteer's own rules
     set beforehand (expect a strong pause with the optional wait).
  3. A small ordinary purchase of ₹2,000 of shares from savings (expect a quiet result).
  4. "What will my SIP of ₹5,000 a month look like over 10 years?" (expect a calculation with
     several scenarios, labelled an illustration).
  5. "I already paid ₹5,000 by UPI and now they want a fee to withdraw" (expect the recovery path).
  6. "Should I buy Reliance?" (expect a refusal that says what Ruko does instead).
- **Time:** about 25 minutes per volunteer, including the consent talk and a 3-question chat at the end.

## 3. Consent text (read aloud, then the volunteer says yes or no)

> This is a short test of an app called Ruko, which helps people pause before a money decision.
> You will try six made-up situations on a phone. No real money moves and nothing you do is advice
> from me or from Ruko. The app keeps your notes on this phone only. If you choose, you can
> download a small summary file that contains only counts, for example how many pauses you read
> to the end. It has no message text, no amounts and no names, and I will not ask for your name.
> You can stop at any time, skip any scenario and delete the app's data from the phone's browser
> settings. Taking part is voluntary. Do you agree to try it?

Hindi and Kannada versions need a native speaker's translation before use (not written here).

## 4. What is recorded

**By the app, on the volunteer's phone, shared only if they choose to:** the anonymised summary
(`Settings → Download my anonymised summary`), which holds only counts:

- decisions by level (L0 to L3) and by action (went ahead, changed amount, waited, planned, dropped)
- pauses shown, read through, could say why, changed their mind after
- overrides with and without a stated reason
- cooling-off waits offered and skipped
- the optional one-tap "how did that pause feel" (helpful, fine, annoying), asked at most once a week
- recovery checklist items ticked
- how many entries came from the fictional broker demo

**By the facilitator, on paper, without names:** a volunteer code (P01, P02, ...), the arm order,
language, and for each scenario and arm a tick for "could say why the pause appeared in their own
words" and a note of the one-sentence reason. No photos, audio or screen recordings.

**Never recorded:** names, phone numbers, message text, amounts, screenshots, voice, location,
device identifiers.

**Hosting note:** if the backend runs on a cloud host, the host's own request logs can include
network addresses and timings even though Ruko's app logs do not (`docs/deploy_cloud_run.md`, "Logging and privacy").
Say so in the consent talk, or switch the host's request logging to the minimum, before the pilot.

## 5. Procedure for one session

1. Consent talk (above). Give the volunteer a code. Choose the arm order by a coin toss.
2. Set the volunteer's own rules first (Home → My rules): for scenario 2 they pick a share of savings
   they would never exceed and a wait they would want. Leave "safe defaults" for anyone who declines.
3. Run each scenario in both arms. Do not explain the app. If asked what something means, answer
   "what does it look like it means to you?" and note the answer.
4. After each pause, if the app asks how it felt, the volunteer may tap an answer or skip it.
5. Three questions at the end, in the volunteer's language: Which pause was most useful? Which was
   most annoying? Was anything unclear or too long?
6. Offer the summary download. If they agree, they send the file to the facilitator; delete it from
   their phone afterwards if they wish.

## 6. Analysis (descriptive only)

- Report counts per arm and per scenario, never percentages without the count beside them.
- Pause read-through, comprehension, reconsideration, overrides with a reason, annoyance ratings
  and wait skips are shown side by side for arm A and arm B.
- Read the free-text answers for confusion and for wording that sounded like a verdict or advice
  (a guardrail failure of tone, even though the text is templated).
- Do not test for significance, do not rank volunteers, do not compare against anyone's outcomes.
- State the limits plainly: small group, friendly volunteers, made-up scenarios, the same author
  wrote the scenarios and the system.

## 7. Data handling

- Summary files and paper notes carry codes, not names. Keep them in one private folder.
- Delete the raw files after the write-up; keep only the table of counts.
- Anyone can ask for their file to be deleted at any time.

## 8. Before the pilot

- [ ] Owner reviews this protocol and the consent text.
- [ ] Native-speaker translation of the consent text and of the app's Hindi and Kannada drafts.
- [ ] Facts the scenarios rely on are verified (`docs/data_sources.md`), or the pilot runs in the
      development configuration and says so.
- [ ] A device test of the installed app on Android (`frontend/README.md`).
- [ ] Decide whether to build an in-app fixed-prompt switch for arm B.
