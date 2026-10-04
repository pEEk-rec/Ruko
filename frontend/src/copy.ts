// Frontend chrome text (buttons, labels, empty and error states). Everything Ruko *says about
// a decision* comes from the backend's rendered templates instead. English only for now;
// Hindi and Kannada are added as further entries in this map (a data task).

import type { AppErrorKind } from "./services/api";
import type { InterventionLevel, JournalAction, Locale } from "./types/api";

const en = {
  privateByDesign: "Private by design",
  homeEyebrow: "Your decision space",
  homeTitle: "Before you act, take a moment.",
  homeBody:
    "A calm place to think through a financial decision. Ruko helps you pause; the choice stays yours.",
  shareSomething: "Share something",
  shareHint: "Bring in only what you choose to share.",
  thinkDecision: "Think through a decision",
  myRules: "My rules",
  myRulesHint: "Your commitments, on your terms",
  journal: "Journal",
  journalHint: "Look back at a decision",
  homeFooter: "Only what you share is analyzed · No broker, OTP or SMS access",

  composeEyebrow: "Shared with Ruko",
  composeDecisionEyebrow: "Think through a decision",
  composeLabel: "Paste the message you received",
  composeDecisionLabel: "What are you thinking of doing?",
  composePlaceholder: "Paste or type the message here",
  composeAddScreenshot: "Add a screenshot instead",
  composeRemoveScreenshot: "Remove screenshot",
  composeScreenshotChosen: "Screenshot added",
  composeSubmit: "Look at this",
  composeEmpty: "Paste a message or add a screenshot first.",
  composeFooter: "Ruko only reviews content you choose to share. Never paste OTPs, PINs or passwords.",
  messageYouReceived: "A message you received",
  back: "Back",

  processingTitle: "Looking at what you shared…",
  processingBody: "Understanding the message and its signals.",

  clarifyEyebrow: "A quick question",
  clarifyAmountPlaceholder: "Amount in ₹",
  clarifyAmountInvalid: "Enter a whole rupee amount, like 20000.",
  clarifyNumberPlaceholder: "Number",
  clarifyNumberInvalid: "Enter a whole number, like 12.",
  clarifyNext: "Next",
  clarifySkip: "Prefer not to say",
  clarifyFooter: "Ruko asks only what it needs. Your answers stay with this decision.",

  levelEyebrow: {
    L0: "Nothing stood out",
    L1: "A small nudge",
    L2: "A moment before action",
    L3: "A deliberate pause",
  } satisfies Record<InterventionLevel, string>,
  whatISee: "What I see",
  yourContext: "Your context",
  cannotTell: "Ruko can't tell from a message alone whether an offer is genuine.",
  learnWhy: "Learn why this matters",
  thinkThrough: "Think this through",
  learn: "Learn",
  continue: "Continue",
  pauseFooterL1: "Ruko doesn't decide for you.",
  pauseFooter: "You remain in control of what happens next.",
  coolingOff: (minutes: number) => `If helpful, take ${minutes} minutes before continuing.`,

  learnEyebrow: "Why this matters",
  asOf: (date: string) => `As of ${date}`,
  unverified: "Not yet checked by a person",
  source: "Source",

  reflectEyebrow: "A brief reflection",
  reflectTitle: "What makes you want to do this?",
  reflectBody: "Choose what feels closest. You can keep it brief.",
  reflectChoices: [
    "Someone recommended it",
    "I'm afraid of missing out",
    "I understand the opportunity",
    "I want quick returns",
    "Something else",
  ],
  reflectOwnWords: "Or say it in your own words",
  reflectPlaceholder: "Write a thought…",
  reflectSkip: "You can also skip this step",
  reflectSkipButton: "Skip",

  decideEyebrow: "Your decision",
  decideTitle: "What will you do?",
  decideBody: "Whatever you choose is your call.",
  actions: {
    went_ahead: "Go ahead",
    delayed: "Wait for now",
    changed_amount: "Change the amount",
    dropped: "Not do it",
    set_plan: "Make a plan first",
  } satisfies Record<JournalAction, string>,
  actionPast: {
    went_ahead: "I chose to go ahead.",
    delayed: "I chose to wait.",
    changed_amount: "I chose to change the amount.",
    dropped: "I chose not to do it.",
    set_plan: "I chose to make a plan first.",
  } satisfies Record<JournalAction, string>,

  journalEyebrow: "Your journal",
  journalSavedTitle: "Decision recorded.",
  journalSavedBody: "A note for your future self.",
  whatIConsidered: "What I considered",
  why: "Why",
  myDecision: "My decision",
  journalOutro: "Your decisions stay yours. Ruko is here when you want a moment to think.",
  done: "Done",
  dontKeep: "Don't keep this note",
  journalFooter: "Journal is optional and private to you. It stays on this phone.",
  journalEmpty: "No decisions yet. When you think one through, a short note can be kept here.",
  aScreenshot: "A screenshot",
  notStated: "Not written down",

  reportEyebrow: "What the message shows",
  nothingFound: "Nothing to report",
  glossaryEyebrow: "Explained simply",
  recoveryEyebrow: "Getting help",
  recoveryUrgent: "Do this now",
  recoveryEvidence: "Keep this evidence",
  recoveryDraft: "Draft complaint (you send it yourself)",
  copy: "Copy",
  copied: "Copied",
  refusalEyebrow: "Something Ruko doesn't do",
  calcEyebrow: "The arithmetic",
  calcAssumptions: "Assumptions",
  shareSomethingElse: "Share something else",
  home: "Home",
  recoveryOpen: "Get help now",

  rulesEyebrow: "My rules",
  rulesTitle: "Your commitments, on your terms.",
  rulesBody: "Optional. Saved only on this phone and sent with each check so Ruko can compare.",
  expenses: "Monthly expenses",
  savings: "Savings you can reach quickly",
  maxShare: "At most this % of my savings in one decision",
  noBorrowed: "I don't invest borrowed money",
  coolingRule: "Minutes I want to wait before acting",
  notSet: "Not set",
  save: "Save",
  saved: "Saved on this phone",
  saveFailed: "This phone didn't allow saving.",

  errorEyebrow: "Something went wrong",
  errors: {
    backend_unavailable: "Ruko can't be reached right now. Check your connection and try again.",
    timeout: "This is taking longer than usual. Please try again.",
    invalid_response: "Ruko got an answer it couldn't read. Please try again.",
    unsupported_input: "Ruko can't read this kind of file. Try pasting the text instead.",
    reading_unavailable:
      "Ruko can't read screenshots or voice right now. Try pasting the text instead.",
    too_many_requests: "Too many checks in a short time. Wait a minute and try again.",
    invalid_request: "Ruko couldn't use that input. Try pasting the message again.",
    server_error: "Something went wrong on Ruko's side. Please try again.",
  } satisfies Record<AppErrorKind, string>,
  tryAgain: "Try again",
  startOver: "Start over",
};

export type Copy = typeof en;

const copies: Record<Locale, Copy> = { en, hi: en, kn: en };

/** Frontend chrome text for a locale (falls back to English until translated). */
export function copyFor(locale: Locale): Copy {
  return copies[locale] ?? en;
}
