// Application state for one decision flow, as a plain reducer.
// The state only records what the backend returned and what the user chose; it never
// computes a level, a signal or a verdict.

import type { AppErrorKind } from "../services/api";
import type {
  AnalyzeResponse,
  CalculationInputs,
  ClarifyResponse,
  DecisionAnswers,
  DecisionPlan,
  JournalAction,
  PauseResponse,
  RawInput,
} from "../types/api";

export type Screen =
  | "onboarding"
  | "settings"
  | "recover_form"
  | "plan"
  | "calculator"
  | "mirror"
  | "home"
  | "compose"
  | "processing"
  | "clarify"
  | "result"
  | "learn"
  | "learn_hub"
  | "lesson"
  | "reflect"
  | "decide"
  | "journal_saved"
  | "journal"
  | "rules"
  | "error";

/** Whether the user arrived by sharing, or chose "think through a decision". */
export type EntryMode = "share" | "decision";

/** How the content reached Ruko (for the journal note and for resending after a question). */
export type InputKind = "text" | "image" | "voice";

/** An L3 cooling-off wait: how long it was and whether the user skipped it (always allowed). */
export interface CoolingOff {
  minutes: number;
  skipped: boolean;
}

export interface Reflection {
  choice: string | null;
  text: string;
}

export interface FlowState {
  screen: Screen;
  entry: EntryMode;
  input: RawInput | null;
  answers: DecisionAnswers;
  response: AnalyzeResponse | null;
  lastClarify: ClarifyResponse | null;
  errorKind: AppErrorKind | null;
  reflection: Reflection | null;
  learned: boolean;
  action: JournalAction | null;
  overrode: boolean;
  inputKind: InputKind;
  coolingOff: CoolingOff | null;
  /** The plan the user wrote for this decision (flags only; the words stay on the device). */
  plan: DecisionPlan | null;
  /** The user changed the amount and re-checked: a way of reconsidering. */
  changedAmount: boolean;
  /** Numbers to start the live calculator with (from a result or a lesson). */
  calcSeed: CalculationInputs | null;
  /** The lesson open on the lesson screen, and the screen its back button returns to. */
  lessonId: string | null;
  lessonBack: Screen;
}

export const initialState: FlowState = {
  screen: "home",
  entry: "share",
  input: null,
  answers: {},
  response: null,
  lastClarify: null,
  errorKind: null,
  reflection: null,
  learned: false,
  action: null,
  overrode: false,
  inputKind: "text",
  coolingOff: null,
  plan: null,
  changedAmount: false,
  calcSeed: null,
  lessonId: null,
  lessonBack: "learn_hub",
};

/** The state a fresh app starts in: the welcome flow until it was finished or skipped. */
export function initialStateFor(onboarded: boolean): FlowState {
  return onboarded ? initialState : { ...initialState, screen: "onboarding" };
}

export type FlowAction =
  | { type: "go"; screen: Screen }
  | { type: "start"; entry: EntryMode; input?: RawInput | null }
  | { type: "submit"; input: RawInput | null; inputKind: InputKind; answers: DecisionAnswers }
  | { type: "received"; response: AnalyzeResponse }
  | { type: "failed"; errorKind: AppErrorKind }
  | { type: "learned" }
  | { type: "cooling"; coolingOff: CoolingOff }
  | { type: "planned"; plan: DecisionPlan }
  | { type: "amount_changed" }
  | { type: "calculator"; seed: CalculationInputs | null }
  | { type: "lesson"; id: string; back: Screen }
  | { type: "reflected"; reflection: Reflection }
  | { type: "decided"; action: JournalAction; overrode: boolean }
  | { type: "reset" };

/** Advance the flow. Each backend response kind maps to exactly one screen. */
export function flowReducer(state: FlowState, action: FlowAction): FlowState {
  switch (action.type) {
    case "go":
      return { ...state, screen: action.screen };
    case "start":
      return { ...initialState, screen: "compose", entry: action.entry, input: action.input ?? null };
    case "submit":
      return {
        ...state,
        screen: "processing",
        input: action.input,
        inputKind: action.inputKind,
        answers: action.answers,
        errorKind: null,
      };
    case "received": {
      const isClarify = action.response.kind === "clarify";
      return {
        ...state,
        response: action.response,
        lastClarify: isClarify ? (action.response as ClarifyResponse) : state.lastClarify,
        screen: isClarify ? "clarify" : "result",
      };
    }
    case "failed":
      return { ...state, screen: "error", errorKind: action.errorKind };
    case "learned":
      return { ...state, learned: true, screen: "learn" };
    case "cooling":
      return { ...state, coolingOff: action.coolingOff };
    case "planned":
      return { ...state, plan: action.plan };
    case "amount_changed":
      return { ...state, changedAmount: true };
    case "calculator":
      return { ...initialState, screen: "calculator", calcSeed: action.seed };
    case "lesson":
      return { ...state, screen: "lesson", lessonId: action.id, lessonBack: action.back };
    case "reflected":
      return { ...state, reflection: action.reflection, screen: "decide" };
    case "decided":
      return { ...state, action: action.action, overrode: action.overrode, screen: "journal_saved" };
    case "reset":
      return { ...initialState, screen: "home" };
  }
}

/** The pause response currently shown, if the flow reached one. */
export function currentPause(state: FlowState): PauseResponse | null {
  return state.response?.kind === "pause" ? state.response : null;
}
