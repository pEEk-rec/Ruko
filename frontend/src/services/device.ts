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

/** Notes that never leave the device (not part of any backend contract). */
export interface JournalNotes {
  shared_excerpt: string;
  reflection_choice: string | null;
  reflection_text: string;
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

/** Remember which explanation cards were seen, so the backend can fade them. */
export function markCardsSeen(cardIds: string[]): void {
  if (cardIds.length === 0) return;
  const profile = loadProfile();
  const seen = new Set(profile.seen_card_ids ?? []);
  cardIds.forEach((id) => seen.add(id));
  saveProfile({ ...profile, seen_card_ids: [...seen].slice(-200) });
}
