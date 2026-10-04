// Builds the device journal record for a finished decision. Bookkeeping only: it copies
// what the backend showed and what the user chose; it judges nothing.

import type { JournalRecord } from "../services/device";
import type { FlowState } from "./flow";

const EXCERPT_LENGTH = 140;

function newId(): string {
  const random = Math.random().toString(36).slice(2, 10);
  return `j${Date.now().toString(36)}${random}`.slice(0, 40);
}

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

/** Return a journal record for the flow, or null if no decision was made yet. */
export function buildJournalRecord(state: FlowState): JournalRecord | null {
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
      reflection_choice: state.reflection?.choice ?? null,
      reflection_text: state.reflection?.text ?? "",
    },
  };
}
