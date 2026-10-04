// The profile snapshot sent with each request: what the user saved, plus the attention counts
// the backend profile expects ("counted on the device", src/ruko/models/profile.py). These are
// plain counts of past journal entries; the backend alone decides what they mean.

import type { UserProfile } from "../types/api";
import { loadJournal, loadProfile, type JournalRecord } from "./device";

const DAY_MS = 86_400_000;

/** Count recent interventions and the current rules-followed streak from journal records. */
export function attentionFromJournal(
  records: JournalRecord[],
  now: Date = new Date(),
): NonNullable<UserProfile["attention"]> {
  const cutoff = now.getTime() - 7 * DAY_MS;
  let l1 = 0;
  let l2 = 0;
  let l3 = 0;
  for (const { entry } of records) {
    if (new Date(entry.date).getTime() < cutoff) continue;
    if (entry.level_shown === "L1") l1 += 1;
    if (entry.level_shown === "L2") l2 += 1;
    if (entry.level_shown === "L3") l3 += 1;
  }
  let streak = 0;
  for (const { entry } of records) {
    if (!entry.followed_own_rules) break;
    streak += 1;
  }
  return {
    l1_this_week: l1,
    l2_this_week: l2,
    l3_this_week: l3,
    rule_following_streak: streak,
  };
}

/** The saved profile with fresh attention counts, ready to send. */
export function profileForRequest(): UserProfile {
  return { ...loadProfile(), attention: attentionFromJournal(loadJournal()) };
}
