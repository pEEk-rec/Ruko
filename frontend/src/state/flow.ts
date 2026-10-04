// Application state for one decision flow, as a plain reducer.
// The state only records what the backend returned and what the user chose; it never
// computes a level, a signal or a verdict.

import type { AppErrorKind } from "../services/api";
import type {
  AnalyzeResponse,
  ClarifyResponse,
  DecisionAnswers,
  JournalAction,
  PauseResponse,
  RawInput,
} from "../types/api";

export type Screen =
  | "home"
  | "compose"
  | "processing"
  | "clarify"
  | "result"
  | "learn"
  | "reflect"
  | "decide"
  | "journal_saved"
  | "journal"
  | "rules"
  | "error";

/** Whether the user arrived by sharing, or chose "think through a decision". */
export type EntryMode = "share" | "decision";

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
};

export type FlowAction =
  | { type: "go"; screen: Screen }
  | { type: "start"; entry: EntryMode; input?: RawInput | null }
  | { type: "submit"; input: RawInput; answers: DecisionAnswers }
  | { type: "received"; response: AnalyzeResponse }
  | { type: "failed"; errorKind: AppErrorKind }
  | { type: "learned" }
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
    case "reflected":
      return { ...state, reflection: action.reflection, screen: "decide" };
    case "decided":
      return { ...state, action: action.action, overrode: action.overrode, screen: "journal_saved" };
    case "reset":
      return initialState;
  }
}

/** The pause response currently shown, if the flow reached one. */
export function currentPause(state: FlowState): PauseResponse | null {
  return state.response?.kind === "pause" ? state.response : null;
}
