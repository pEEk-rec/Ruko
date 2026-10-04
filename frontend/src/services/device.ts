// Device-only storage for the profile and journal. Nothing here is sent anywhere except the
// profile snapshot that travels with each analyze request (the backend is stateless).
// Storage can be unavailable (private mode); every access is wrapped and falls back safely.

import type {
  DecisionStage,
  InterventionLevel,
  JournalAction,
  ProductClass,
  SourceType,
  UserProfile,
} from "../types/api";
import { MAX_SEEN_IDS } from "../config/defaults";

const PROFILE_KEY = "ruko.profile.v1";
const JOURNAL_KEY = "ruko.journal.v1";

/** Fields that match the backend's JournalEntry (models/journal.py), for /v1/journal/review. */
export interface JournalEntryData {
  id: string;
  date: string;
  stage: DecisionStage;
  product_class: ProductClass;
  amount_inr?: number;
  source_type: SourceType;
  level_shown: InterventionLevel;
  reason_codes: string[];
  action: JournalAction;
  overrode: boolean;
  override_reason_given: boolean;
  pause_completed: boolean | null;
  could_state_why: boolean | null;
  followed_own_rules: boolean;
}

/** How a pause felt, one tap, optional (impact measure; stays on the device). */
export type PauseFeeling = "helpful" | "fine" | "annoying";

/** The cooling-off wait for an L3 pause: how long it was and whether the user skipped it. */
export interface CoolingOffNote {
  minutes: number;
  skipped: boolean;
}

/** Notes that never leave the device (not part of any backend contract). */
export interface JournalNotes {
  shared_excerpt: string;
  /** How the content reached Ruko: typed or pasted, a screenshot, or a voice note. */
  input_kind?: "text" | "image" | "voice";
  reflection_choice: string | null;
  reflection_text: string;
  /** Present when an L3 pause offered a wait. */
  cooling_off?: CoolingOffNote | null;
  /** Optional one-tap rating after a pause (asked at most once a week). */
  feeling?: PauseFeeling | null;
  /** Where the decision came from: the app flow or the fictional broker demo. */
  origin?: "app" | "broker_demo";
}

export interface JournalRecord {
  entry: JournalEntryData;
  notes: JournalNotes;
}

function readJson<T>(key: string, fallback: T): T {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function writeJson(key: string, value: unknown): boolean {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}

/** Load the device profile (empty if none saved). */
export function loadProfile(): UserProfile {
  return readJson<UserProfile>(PROFILE_KEY, {});
}

/** Save the device profile. Returns false if the device refused storage. */
export function saveProfile(profile: UserProfile): boolean {
  return writeJson(PROFILE_KEY, profile);
}

/** Load journal records, newest first. */
export function loadJournal(): JournalRecord[] {
  const records = readJson<JournalRecord[]>(JOURNAL_KEY, []);
  return Array.isArray(records) ? records : [];
}

/** Add one journal record at the top. Returns false if storage failed. */
export function addJournalRecord(record: JournalRecord): boolean {
  return writeJson(JOURNAL_KEY, [record, ...loadJournal()].slice(0, 1000));
}

/** Replace the saved journal (used when the user edits a note, e.g. the weekly rating). */
export function saveJournal(records: JournalRecord[]): boolean {
  return writeJson(JOURNAL_KEY, records.slice(0, 1000));
}

function markSeen(field: "seen_card_ids" | "seen_lesson_ids", ids: string[]): void {
  if (ids.length === 0) return;
  const profile = loadProfile();
  const seen = new Set(profile[field] ?? []);
  ids.forEach((id) => seen.add(id));
  saveProfile({ ...profile, [field]: [...seen].slice(-MAX_SEEN_IDS) });
}

/** Remember which explanation cards were seen, so the backend can fade them. */
export function markCardsSeen(cardIds: string[]): void {
  markSeen("seen_card_ids", cardIds);
}

/** Remember which lessons were seen, so the backend can fade them. */
export function markLessonsSeen(lessonIds: string[]): void {
  markSeen("seen_lesson_ids", lessonIds);
}

/** Recovery checklist ticks, per scenario, stored on the device (item indexes). */
const EVIDENCE_KEY = "ruko.evidence.v1";

export function loadEvidence(scenario: string): number[] {
  const all = readJson<Record<string, number[]>>(EVIDENCE_KEY, {});
  const ticked = all[scenario];
  return Array.isArray(ticked) ? ticked.filter((n) => Number.isInteger(n)) : [];
}

/** Save the ticked checklist items for a scenario. Returns false if storage failed. */
export function saveEvidence(scenario: string, ticked: number[]): boolean {
  const all = readJson<Record<string, number[]>>(EVIDENCE_KEY, {});
  return writeJson(EVIDENCE_KEY, { ...all, [scenario]: [...new Set(ticked)].sort() });
}

/** Every scenario's ticks (used by the anonymised summary: counts only). */
export function loadAllEvidence(): Record<string, number[]> {
  return readJson<Record<string, number[]>>(EVIDENCE_KEY, {});
}
