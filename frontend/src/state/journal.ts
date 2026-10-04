// Builds the device journal record for a finished decision. Bookkeeping only: it copies
// what the backend showed and what the user chose; it judges nothing.

import type { CoolingOffNote, JournalRecord, PauseFeeling } from "../services/device";
import type { PauseResponse } from "../types/api";
import type { FlowState } from "./flow";

const EXCERPT_LENGTH = 140;

/** A short device-generated entry ID (works without secure-context APIs). */
export function newId(): string {
  const random = Math.random().toString(36).slice(2, 10);
  return `j${Date.now().toString(36)}${random}`.slice(0, 40);
}

/** Today's date as YYYY-MM-DD (the backend's journal date is a plain date). */
export function today(): string {
  return new Date().toISOString().slice(0, 10);
}

/**
 * The wait an L3 pause offered, and whether the user took it. Leaving the pause without
 * finishing the wait counts as skipping it (the choice to continue is always theirs).
 */
function coolingNote(state: FlowState, pause: PauseResponse | null): CoolingOffNote | null {
  const offered = pause?.decision.cooling_off_minutes;
  if (!pause || pause.level !== "L3" || !offered) return null;
  return { minutes: offered, skipped: state.coolingOff?.skipped ?? true };
}

/** Return a journal record for the flow, or null if no decision was made yet. */
export function buildJournalRecord(
  state: FlowState,
  feeling: PauseFeeling | null = null,
): JournalRecord | null {
  if (!state.action) return null;
  const pause = state.response?.kind === "pause" ? state.response : null;
  const reasonCodes = pause ? pause.decision.reasons.map((r) => r.code) : [];
  const ruleReasonShown = reasonCodes.some((code) => code.startsWith("RULE_"));
  // Prefer the pause's own event summary; fall back to what clarify understood.
  const event = pause?.event ?? state.lastClarify?.event;
  const reflected = state.reflection !== null;
  const statedWhy = reflected && (!!state.reflection?.choice || !!state.reflection?.text.trim());

  return {
    entry: {
      id: newId(),
      date: today(),
      stage: state.response?.meta.stage ?? "consider_action",
      product_class: state.answers.product_class ?? event?.product_class ?? "unknown",
      amount_inr: state.answers.amount_inr,
      source_type: state.answers.source_type ?? event?.source_type ?? "unknown",
      level_shown: pause?.level ?? "L0",
      reason_codes: reasonCodes,
      action: state.action,
      overrode: state.overrode,
      override_reason_given: state.overrode && statedWhy,
      pause_completed: pause && pause.level !== "L0" ? reflected : null,
      could_state_why: reflected ? statedWhy : null,
      followed_own_rules: !(ruleReasonShown && state.action === "went_ahead"),
    },
    notes: {
      shared_excerpt: (state.input?.type === "image" ? "" : state.input?.content ?? "").slice(
        0,
        EXCERPT_LENGTH,
      ),
      input_kind: state.inputKind,
      reflection_choice: state.reflection?.choice ?? null,
      reflection_text: state.reflection?.text ?? "",
      cooling_off: coolingNote(state, pause),
      feeling,
      origin: "app",
    },
  };
}

const WEEK_MS = 7 * 86_400_000;

/**
 * Whether to offer the one-tap "how did that pause feel?" rating: only after a pause, and at
 * most once a week (no rating among the last seven days of journal entries).
 */
export function shouldAskFeeling(
  level: string | undefined,
  records: JournalRecord[],
  now: Date = new Date(),
): boolean {
  if (!level || level === "L0") return false;
  return !records.some(
    (r) => r.notes.feeling && now.getTime() - new Date(r.entry.date).getTime() < WEEK_MS,
  );
}
