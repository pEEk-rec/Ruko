// Grouping what a message does (pushes you to act, makes promises, says where it came from) so a
// long list of flags reads as "what is this doing to me?". Pure: it only reorders and labels
// what the backend sent; it never changes a certainty or a level.

import type { SignalView } from "../types/api";

export interface SignalGroup {
  /** The backend's rendered heading, or null when the list is short enough not to need one. */
  label: string | null;
  signals: SignalView[];
}

/** Fewer signals than this read fine as one list. */
export const GROUP_FROM = 3;

export function groupSignals(signals: SignalView[]): SignalGroup[] {
  const labels = new Set(signals.map((s) => s.role_label).filter(Boolean));
  if (signals.length < GROUP_FROM || labels.size < 2) return [{ label: null, signals }];
  const order: string[] = [];
  const byLabel = new Map<string, SignalView[]>();
  for (const signal of signals) {
    const label = signal.role_label ?? "";
    if (!byLabel.has(label)) {
      byLabel.set(label, []);
      order.push(label);
    }
    byLabel.get(label)!.push(signal);
  }
  return order.map((label) => ({ label: label || null, signals: byLabel.get(label)! }));
}
