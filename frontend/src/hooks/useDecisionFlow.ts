// Connects the flow reducer to the backend and the device store.

import { useCallback, useReducer, useRef } from "react";
import { analyze, analyzeVoice, AppError, recover } from "../services/api";
import {
  addJournalRecord,
  markCardsSeen,
  markLessonsSeen,
  type PauseFeeling,
} from "../services/device";
import { profileForRequest } from "../services/profile";
import type { Recorded } from "../services/recorder";
import { flowReducer, initialStateFor, type CoolingOff, type FlowState } from "../state/flow";
import { buildJournalRecord } from "../state/journal";
import { mergeAnswers } from "../state/answers";
import type {
  DecisionAnswers,
  JournalAction,
  Locale,
  RawInput,
  RecoveryAnswers,
} from "../types/api";

/** What was last sent, kept in memory only so a clarify answer or a retry can resend it. */
type LastRequest =
  | { kind: "text"; input: RawInput }
  | { kind: "voice"; recorded: Recorded }
  | { kind: "recovery"; answers: RecoveryAnswers };

export function useDecisionFlow(locale: Locale, initial?: FlowState) {
  const [state, dispatch] = useReducer(flowReducer, initial ?? initialStateFor(true));
  const last = useRef<LastRequest | null>(null);

  const run = useCallback(
    async (request: LastRequest, answers: DecisionAnswers) => {
      last.current = request;
      const input = request.kind === "text" ? request.input : null;
      const inputKind =
        request.kind === "voice" ? "voice" : input?.type === "image" ? "image" : "text";
      dispatch({ type: "submit", input, inputKind, answers });
      try {
        let response;
        if (request.kind === "voice") {
          response = await analyzeVoice({
            audio_base64: request.recorded.base64,
            audio_format: request.recorded.format,
            speech_locale: locale,
            locale,
            profile: profileForRequest(),
            answers,
          });
        } else if (request.kind === "recovery") {
          response = await recover({ locale, answers: request.answers });
        } else {
          response = await analyze({
            input: request.input,
            locale,
            profile: profileForRequest(),
            answers,
          });
        }
        dispatch({ type: "received", response });
      } catch (err) {
        dispatch({ type: "failed", errorKind: err instanceof AppError ? err.kind : "server_error" });
      }
    },
    [locale],
  );

  /** Send the shared input (with any answers so far) to /v1/analyze. */
  const submit = useCallback(
    (input: RawInput, answers: DecisionAnswers) => run({ kind: "text", input }, answers),
    [run],
  );

  /** Send a recorded voice note to /v1/analyze/voice. */
  const submitVoice = useCallback(
    (recorded: Recorded, answers: DecisionAnswers) => run({ kind: "voice", recorded }, answers),
    [run],
  );

  /** Send the recovery form's answers to /v1/recover. */
  const submitRecovery = useCallback(
    (answers: RecoveryAnswers) => run({ kind: "recovery", answers }, {}),
    [run],
  );

  /** Resend the same content with the user's clarify answers merged in. */
  const answer = useCallback(
    (extra: DecisionAnswers) => {
      if (last.current) void run(last.current, mergeAnswers(state.answers, extra));
    },
    [state.answers, run],
  );

  /** Resend the same content with the stage forced to "already acted" (the recovery path). */
  const recoverFromResult = useCallback(() => {
    if (last.current && last.current.kind !== "recovery") {
      void run(last.current, { ...state.answers, stage: "already_acted" });
    }
  }, [state.answers, run]);

  /** Retry the last request after an error. */
  const retry = useCallback(() => {
    if (last.current) void run(last.current, state.answers);
    else dispatch({ type: "go", screen: "compose" });
  }, [state.answers, run]);

  /** Record that the user skipped or sat through an L3 wait. */
  const noteCooling = useCallback((coolingOff: CoolingOff) => {
    dispatch({ type: "cooling", coolingOff });
  }, []);

  /** Note the user's decision (always theirs) and show the journal summary. */
  const decide = useCallback((action: JournalAction, overrode: boolean) => {
    dispatch({ type: "decided", action, overrode });
  }, []);

  /** Finish the flow; keep the journal record on the device only if the user chose to. */
  const finish = useCallback(
    (keep: boolean, feeling: PauseFeeling | null = null) => {
      const record = keep ? buildJournalRecord(state, feeling) : null;
      if (record) addJournalRecord(record);
      if (state.response?.kind === "pause") markCardsSeen(state.response.cards.map((c) => c.id));
      const shown =
        state.response?.kind === "pause" ||
        state.response?.kind === "calculation" ||
        state.response?.kind === "content_report"
          ? (state.response.lessons ?? [])
          : [];
      markLessonsSeen(shown.filter((lesson) => !lesson.safety_critical).map((lesson) => lesson.id));
      last.current = null;
      dispatch({ type: "reset" });
    },
    [state],
  );

  /** Forget the in-memory request (used when going home). */
  const forget = useCallback(() => {
    last.current = null;
  }, []);

  return {
    state,
    dispatch,
    submit,
    submitVoice,
    submitRecovery,
    answer,
    recoverFromResult,
    retry,
    noteCooling,
    decide,
    finish,
    forget,
  };
}
