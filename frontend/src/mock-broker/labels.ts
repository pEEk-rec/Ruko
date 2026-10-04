// How the fictional broker words the reason codes Ruko returns. A real broker would write its
// own text; the backend deliberately sends codes only (docs/broker_embedding_spec.md). Each
// line only restates what the user declared or set for themselves. None judges the order.

import type { InterventionLevel } from "../types/api";

export const REASON_LABELS: Record<string, string> = {
  RULE_MAX_SHARE_EXCEEDED: "This order is above the share of your savings that you set as your own limit.",
  RULE_MAX_AMOUNT_EXCEEDED: "This order is above the rupee limit you set for yourself.",
  BORROWED_FUNDS: "You marked this order as using borrowed money.",
  PROTECTED_GOAL_FUNDS: "This money is set aside for a goal you chose to protect.",
  EMERGENCY_FUNDS: "This money is part of your emergency funds.",
  FIRST_TIME_PRODUCT: "You said you are new to this kind of product.",
  LEVERAGED_PRODUCT: "This order uses leverage.",
  PLAN_INCOMPLETE: "The plan you wrote for this kind of order is missing a part.",
  PLAN_DEVIATION: "This order differs from the plan you wrote.",
  UNPLANNED_DECISION: "You have not written a plan for this kind of order.",
  POST_LOSS_REENTRY_DECLARED: "You said you recently took a loss.",
  HIGH_FREQUENCY_DECLARED: "You said you have made many trades this week.",
};

/** The line for a reason code; unknown codes get a calm generic line, never the raw code. */
export function reasonLabel(code: string): string {
  return REASON_LABELS[code] ?? "Ruko noted something about this order.";
}

export const LEVEL_HEADLINES: Record<Exclude<InterventionLevel, "L0">, string> = {
  L1: "A quick check before you place this order.",
  L2: "A moment before you place this order.",
  L3: "Please take a deliberate pause before you place this order.",
};
