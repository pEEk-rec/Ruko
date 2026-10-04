// "Download my anonymised summary": counts only, for a pilot, if the user chooses to share it.
// It contains no message text, no excerpts, no reflections, no rupee amounts, no entry IDs and
// no entry dates: only how many of each kind of thing happened. Everything is computed on the
// device from the journal and the evidence ticks; nothing is uploaded.

import { loadAllEvidence, loadJournal, type JournalRecord } from "./device";

export interface AnonymisedSummary {
  format: "ruko-anonymised-summary";
  version: 1;
  generated_on: string;
  decisions: number;
  by_level: Record<"L0" | "L1" | "L2" | "L3", number>;
  by_action: Record<"went_ahead" | "changed_amount" | "delayed" | "set_plan" | "dropped", number>;
  pauses: number;
  pauses_read_through: number;
  could_state_why: number;
  reconsidered_after_pause: number;
  overrides_with_reason: number;
  overrides_without_reason: number;
  cooling_off_offered: number;
  cooling_off_skipped: number;
  pause_feeling: Record<"helpful" | "fine" | "annoying", number>;
  from_broker_demo: number;
  recovery_checklists_started: number;
  recovery_items_ticked: number;
}

const RECONSIDERED = new Set(["changed_amount", "delayed", "set_plan", "dropped"]);

/** Count the journal and evidence ticks. Pure: the same input always gives the same summary. */
export function buildSummary(
  records: JournalRecord[],
  evidence: Record<string, number[]>,
  generatedOn: string,
): AnonymisedSummary {
  const summary: AnonymisedSummary = {
    format: "ruko-anonymised-summary",
    version: 1,
    generated_on: generatedOn,
    decisions: records.length,
    by_level: { L0: 0, L1: 0, L2: 0, L3: 0 },
    by_action: { went_ahead: 0, changed_amount: 0, delayed: 0, set_plan: 0, dropped: 0 },
    pauses: 0,
    pauses_read_through: 0,
    could_state_why: 0,
    reconsidered_after_pause: 0,
    overrides_with_reason: 0,
    overrides_without_reason: 0,
    cooling_off_offered: 0,
    cooling_off_skipped: 0,
    pause_feeling: { helpful: 0, fine: 0, annoying: 0 },
    from_broker_demo: 0,
    recovery_checklists_started: 0,
    recovery_items_ticked: 0,
  };
  for (const { entry, notes } of records) {
    summary.by_level[entry.level_shown] += 1;
    summary.by_action[entry.action] += 1;
    const paused = entry.level_shown === "L2" || entry.level_shown === "L3";
    if (paused) {
      summary.pauses += 1;
      if (entry.pause_completed) summary.pauses_read_through += 1;
      if (entry.could_state_why) summary.could_state_why += 1;
      if (RECONSIDERED.has(entry.action)) summary.reconsidered_after_pause += 1;
    }
    if (entry.overrode) {
      if (entry.override_reason_given) summary.overrides_with_reason += 1;
      else summary.overrides_without_reason += 1;
    }
    if (notes.cooling_off) {
      summary.cooling_off_offered += 1;
      if (notes.cooling_off.skipped) summary.cooling_off_skipped += 1;
    }
    if (notes.feeling) summary.pause_feeling[notes.feeling] += 1;
    if (notes.origin === "broker_demo") summary.from_broker_demo += 1;
  }
  const lists = Object.values(evidence).filter((ticks) => ticks.length > 0);
  summary.recovery_checklists_started = lists.length;
  summary.recovery_items_ticked = lists.reduce((sum, ticks) => sum + ticks.length, 0);
  return summary;
}

/** The summary for this device right now, as pretty JSON text. */
export function currentSummaryJson(now: Date = new Date()): string {
  const summary = buildSummary(loadJournal(), loadAllEvidence(), now.toISOString().slice(0, 10));
  return JSON.stringify(summary, null, 2);
}

/** Save the summary as a file on the phone. Returns false if the browser cannot do it. */
export function downloadSummary(now: Date = new Date()): boolean {
  try {
    const blob = new Blob([currentSummaryJson(now)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `ruko-summary-${now.toISOString().slice(0, 10)}.json`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    return true;
  } catch {
    return false;
  }
}
