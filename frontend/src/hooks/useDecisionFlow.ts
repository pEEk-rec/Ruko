// Connects the flow reducer to the backend and the device store.

import { useCallback, useReducer } from "react";
import { analyze, AppError } from "../services/api";
import { addJournalRecord, loadProfile, markCardsSeen } from "../services/device";
import { flowReducer, initialState } from "../state/flow";
import { buildJournalRecord } from "../state/journal";
import { mergeAnswers } from "../state/answers";
import type { DecisionAnswers, JournalAction, Locale, RawInput } from "../types/api";

export function useDecisionFlow(locale: Locale) {
  const [state, dispatch] = useReducer(flowReducer, initialState);

  /** Send the shared input (with any answers so far) to /v1/analyze. */
  const submit = useCallback(
    async (input: RawInput, answers: DecisionAnswers) => {
      dispatch({ type: "submit", input, answers });
      try {
        const response = await analyze({ input, locale, profile: loadProfile(), answers });
        dispatch({ type: "received", response });
      } catch (err) {
        dispatch({ type: "failed", errorKind: err instanceof AppError ? err.kind : "server_error" });
      }
    },
    [locale],
  );

  /** Resend the same input with the user's clarify answers merged in. */
  const answer = useCallback(
    (extra: DecisionAnswers) => {
      if (!state.input) return;
      void submit(state.input, mergeAnswers(state.answers, extra));
    },
    [state.input, state.answers, submit],
  );

  /** Retry the last request after an error. */
  const retry = useCallback(() => {
    if (state.input) void submit(state.input, state.answers);
    else dispatch({ type: "go", screen: "compose" });
  }, [state.input, state.answers, submit]);

  /** Note the user's decision (always theirs) and show the journal summary. */
  const decide = useCallback((action: JournalAction, overrode: boolean) => {
    dispatch({ type: "decided", action, overrode });
  }, []);

  /** Finish the flow; keep the journal record on the device only if the user chose to. */
  const finish = useCallback(
    (keep: boolean) => {
      const record = keep ? buildJournalRecord(state) : null;
      if (record) addJournalRecord(record);
      if (state.response?.kind === "pause") markCardsSeen(state.response.cards.map((c) => c.id));
      dispatch({ type: "reset" });
    },
    [state],
  );

  return { state, dispatch, submit, answer, retry, decide, finish };
}
