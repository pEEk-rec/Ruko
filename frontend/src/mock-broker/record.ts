// The device journal record for one order in the fictional broker demo.

import type { JournalRecord } from "../services/device";
import { newId, today } from "../state/journal";
import type { InterventionLevel, JournalAction, ProductClass } from "../types/api";

/**
 * Build the journal record for a demo order. `overrode` follows the backend's meaning
 * (continued past an L2 or L3 pause); `followed_own_rules` is false only if a rule reason was
 * shown and the user went ahead. The note says plainly that this was a demo.
 */
export function brokerRecord(
  productClass: ProductClass,
  amountInr: number,
  level: InterventionLevel,
  reasonCodes: string[],
  action: JournalAction,
): JournalRecord {
  const paused = level === "L2" || level === "L3";
  const ruleShown = reasonCodes.some((code) => code.startsWith("RULE_"));
  return {
    entry: {
      id: newId(),
      date: today(),
      stage: "about_to_act",
      product_class: productClass,
      amount_inr: amountInr,
      source_type: "unknown",
      level_shown: level,
      reason_codes: reasonCodes,
      action,
      overrode: paused && action === "went_ahead",
      override_reason_given: false,
      pause_completed: paused ? true : null,
      could_state_why: null,
      followed_own_rules: !(ruleShown && action === "went_ahead"),
    },
    notes: {
      shared_excerpt: "Fictional broker demo order",
      input_kind: "text",
      reflection_choice: null,
      reflection_text: "",
      origin: "broker_demo",
    },
  };
}
