// What the home screen should put first for this person, right now. It looks at what they have
// done (decisions they chose to wait on, plans they wrote, whether they have set any rule of
// their own, how much history exists) and picks at most two things worth their attention (and
// only one gentle suggestion, only when nothing else is pending). It
// never invents urgency: a card exists only because of something the person did.

import type { JournalRecord } from "../services/device";
import { dismissedToday, isDue, pendingWaits, type Memory, type Wait } from "../services/memory";
import { ownRulesCount } from "../services/profile";
import type { LessonTopic, UserProfile } from "../types/api";

export type HomeCard =
  | { kind: "wait"; wait: Wait; due: boolean }
  | { kind: "plan"; entryId: string; date: string }
  | { kind: "rules" }
  | { kind: "patterns" }
  | { kind: "learn"; lesson: LessonTopic };

const MAX_CARDS = 2;
const DAY_MS = 86_400_000;
const PATTERNS_AFTER = 3;

export function homeCards(input: {
  memory: Memory;
  journal: JournalRecord[];
  profile: UserProfile;
  now?: Date;
  /** Plan follow-ups the person said "not yet" to in this visit. */
  snoozed?: string[];
  /** The lesson the backend would read next for this person, if it has been fetched. */
  learn?: LessonTopic | null;
}): HomeCard[] {
  const { memory, journal, profile, snoozed = [] } = input;
  const now = input.now ?? new Date();
  const cards: HomeCard[] = [];

  // Waits first: due ones, then the ones still running.
  const waits = pendingWaits(memory);
  const dueFirst = [...waits.filter((w) => isDue(w, now)), ...waits.filter((w) => !isDue(w, now))];
  for (const wait of dueFirst.slice(0, MAX_CARDS)) {
    cards.push({ kind: "wait", wait, due: isDue(wait, now) });
  }

  // A plan written at least a day ago that has not been followed up.
  const planned = journal.find(
    ({ entry }) =>
      entry.plan !== undefined &&
      entry.plan_followed === undefined &&
      !snoozed.includes(entry.id) &&
      now.getTime() - new Date(entry.date).getTime() >= DAY_MS,
  );
  if (planned) cards.push({ kind: "plan", entryId: planned.entry.id, date: planned.entry.date });

  // Suggestions only when nothing the person did is waiting on them: the main action of the
  // app (sharing something) should not sit below a pile of nudges.
  if (cards.length === 0) {
    if (ownRulesCount(profile) === 0 && journal.length >= 1 && !memory.dismissed.includes("rules")) {
      cards.push({ kind: "rules" });
    } else if (journal.length >= PATTERNS_AFTER && !memory.dismissed.includes("patterns")) {
      cards.push({ kind: "patterns" });
    } else if (input.learn && !dismissedToday(memory, "learn", now)) {
      cards.push({ kind: "learn", lesson: input.learn });
    }
  }
  return cards.slice(0, MAX_CARDS);
}
