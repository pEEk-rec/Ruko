// The profile snapshot sent with each request: what the user saved, plus the attention counts
// the backend profile expects ("counted on the device", src/ruko/models/profile.py). These are
// plain counts of past journal entries; the backend alone decides what they mean.

import type { UserProfile } from "../types/api";
import { loadJournal, loadProfile, type JournalRecord } from "./device";
import { isLateNight } from "./clock";
import { freshRecent, loadMemory } from "./memory";

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

/**
 * The saved profile with fresh attention counts, how trading has been lately if the person said
 * so in the last day (declared by them, never observed), and a yes/no for "late at night where
 * you are" from the device clock.
 */
export function profileForRequest(now: Date = new Date()): UserProfile {
  const recent = freshRecent(loadMemory(), now);
  const lateNight = isLateNight(now);
  return {
    ...loadProfile(),
    attention: attentionFromJournal(loadJournal(), now),
    ...(recent || lateNight
      ? {
          recent: {
            ...(recent ? { post_loss: recent.postLoss, trades_this_week: recent.trades } : {}),
            ...(lateNight ? { late_night: true } : {}),
          },
        }
      : {}),
  };
}

/** How many of their own rules the person has written (for the journal's rule measure). */
export function ownRulesCount(profile: UserProfile): number {
  const rules = profile.rules ?? {};
  return [
    rules.max_share_of_savings_pct,
    rules.max_amount_inr,
    rules.no_borrowed_money ? true : undefined,
    rules.cooling_off_minutes,
    (rules.protected_goals ?? []).length > 0 ? true : undefined,
    profile.emergency_buffer_months,
  ].filter((v) => v !== undefined).length;
}
