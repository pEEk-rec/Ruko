// What the app remembers about how this person uses it, on this phone only. It is how the app
// adapts to their pace: it never leaves the device, is never sent to the backend, and never
// judges anything. The backend still decides what a decision means; this only decides how much
// extra effort the app asks of someone who has shown what they find useful.

import type {
  FundingSource,
  InterventionLevel,
  ProductClass,
  TradesPerWeekBand,
} from "../types/api";

const KEY = "ruko.memory.v1";
const HOUR_MS = 3_600_000;
const SAMPLE = 5;
/** "Recently" context (a loss, how often they traded) is only trusted for this long. */
const RECENT_FRESH_HOURS = 24;

/** A decision the user chose to wait on, so the app can ask about it later. */
export interface Wait {
  id: string;
  /** The journal entry this wait belongs to. */
  entryId: string;
  createdAt: string;
  dueAt: string;
  /** A short label from the user's own words (the message excerpt), device only. */
  note: string;
  level: InterventionLevel;
  productClass: ProductClass;
  amountInr?: number;
  status: "waiting" | "revisited" | "let_go";
}

/** The words behind a plan, kept on the device (the backend only learns which parts exist). */
export interface PlanNote {
  reason: string;
  reconsider: string;
  createdAt: string;
}

export interface RecentContext {
  postLoss: boolean;
  trades: TradesPerWeekBand;
  at: string;
}

export interface Memory {
  /** The funding source they chose last time (offered as a "last time" chip, never applied). */
  lastFunding: FundingSource | null;
  /** Whether the last few reflection steps were skipped (true) or used (false), newest last. */
  reflectSkipped: boolean[];
  recent: RecentContext | null;
  waits: Wait[];
  planNotes: Record<string, PlanNote>;
  /** Home suggestions the person said "not now" to. */
  dismissed: string[];
}

export const EMPTY_MEMORY: Memory = {
  lastFunding: null,
  reflectSkipped: [],
  recent: null,
  waits: [],
  planNotes: {},
  dismissed: [],
};

export function loadMemory(): Memory {
  try {
    const raw = window.localStorage.getItem(KEY);
    const stored = raw ? (JSON.parse(raw) as Partial<Memory>) : {};
    return {
      lastFunding: stored.lastFunding ?? null,
      reflectSkipped: Array.isArray(stored.reflectSkipped) ? stored.reflectSkipped.slice(-SAMPLE) : [],
      recent: stored.recent ?? null,
      waits: Array.isArray(stored.waits) ? stored.waits : [],
      planNotes: stored.planNotes && typeof stored.planNotes === "object" ? stored.planNotes : {},
      dismissed: Array.isArray(stored.dismissed) ? stored.dismissed : [],
    };
  } catch {
    return { ...EMPTY_MEMORY };
  }
}

function save(memory: Memory): boolean {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(memory));
    return true;
  } catch {
    return false;
  }
}

/** Apply a change to the stored memory and save it. */
export function updateMemory(change: (memory: Memory) => Memory): Memory {
  const next = change(loadMemory());
  save(next);
  return next;
}

// --- pace -----------------------------------------------------------------------------------

export function rememberFunding(funding: FundingSource | null | undefined): void {
  if (!funding || funding === "unknown") return;
  updateMemory((m) => ({ ...m, lastFunding: funding }));
}

/** Note whether the reflection step was skipped or used. */
export function rememberReflection(skipped: boolean): void {
  updateMemory((m) => ({ ...m, reflectSkipped: [...m.reflectSkipped, skipped].slice(-SAMPLE) }));
}

export interface PaceHints {
  /** The person keeps skipping reflection: go straight to deciding (reflection stays a link). */
  fastDecide: boolean;
}

/** How the app should adapt: three skips among the last five reflection steps means "fast". */
export function paceHints(memory: Memory): PaceHints {
  const skips = memory.reflectSkipped.filter(Boolean).length;
  return { fastDecide: memory.reflectSkipped.length >= 3 && skips >= 3 };
}

// --- "lately" context -------------------------------------------------------------------------

export function rememberRecent(context: Omit<RecentContext, "at">, now: Date = new Date()): void {
  updateMemory((m) => ({ ...m, recent: { ...context, at: now.toISOString() } }));
}

/** The "lately" answer if it is still fresh (a day), else null so the app asks again. */
export function freshRecent(memory: Memory, now: Date = new Date()): RecentContext | null {
  if (!memory.recent) return null;
  const age = now.getTime() - new Date(memory.recent.at).getTime();
  return age >= 0 && age < RECENT_FRESH_HOURS * HOUR_MS ? memory.recent : null;
}

// --- waits ------------------------------------------------------------------------------------

export function addWait(wait: Wait): void {
  updateMemory((m) => ({ ...m, waits: [wait, ...m.waits].slice(0, 20) }));
}

export function resolveWait(id: string, status: "revisited" | "let_go"): void {
  updateMemory((m) => ({
    ...m,
    waits: m.waits.map((w) => (w.id === id ? { ...w, status } : w)),
  }));
}

/** Waits the user has not yet followed up, oldest due first. */
export function pendingWaits(memory: Memory): Wait[] {
  return memory.waits
    .filter((w) => w.status === "waiting")
    .sort((a, b) => a.dueAt.localeCompare(b.dueAt));
}

/** True once a wait's own time has passed (the user's cooling-off minutes, or a day). */
export function isDue(wait: Wait, now: Date = new Date()): boolean {
  return new Date(wait.dueAt).getTime() <= now.getTime();
}

// --- plans ------------------------------------------------------------------------------------

export function addPlanNote(id: string, note: PlanNote): void {
  updateMemory((m) => ({ ...m, planNotes: { ...m.planNotes, [id]: note } }));
}

export function removePlanNote(id: string): void {
  updateMemory((m) => {
    const { [id]: _removed, ...rest } = m.planNotes;
    return { ...m, planNotes: rest };
  });
}

/** Default wait: the user's own cooling-off minutes if they set any, else one day. */
export function waitDueAt(coolingMinutes: number | undefined, now: Date = new Date()): string {
  const ms = coolingMinutes && coolingMinutes > 0 ? coolingMinutes * 60_000 : 24 * HOUR_MS;
  return new Date(now.getTime() + ms).toISOString();
}

/** Remember that the person said "not now" to a Home suggestion for the rest of today. */
export function dismissToday(card: string, now: Date = new Date()): void {
  dismiss(`${card}:${now.toISOString().slice(0, 10)}`);
}

/** True if the person said "not now" to this suggestion today. */
export function dismissedToday(memory: Memory, card: string, now: Date = new Date()): boolean {
  return memory.dismissed.includes(`${card}:${now.toISOString().slice(0, 10)}`);
}

/** Remember that the person said "not now" to a Home suggestion. */
export function dismiss(card: string): void {
  updateMemory((m) => (m.dismissed.includes(card) ? m : { ...m, dismissed: [...m.dismissed, card] }));
}
