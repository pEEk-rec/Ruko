// A to F: the pure logic behind the adaptive app (highlighting, contextual choices, pace,
// memory, home cards, decision options, journal measures).

import { beforeEach, describe, expect, it } from "vitest";
import { copyFor } from "../copy";
import {
  addWait,
  dismiss,
  freshRecent,
  isDue,
  loadMemory,
  paceHints,
  pendingWaits,
  rememberFunding,
  rememberRecent,
  rememberReflection,
  resolveWait,
  waitDueAt,
  type Memory,
  type Wait,
  EMPTY_MEMORY,
} from "../services/memory";
import { loadProfile, saveProfile, type JournalRecord } from "../services/device";
import { ownRulesCount, profileForRequest } from "../services/profile";
import { decisionOptions } from "../screens/FlowScreens";
import { initialState } from "../state/flow";
import { homeCards } from "../state/home";
import { buildJournalRecord } from "../state/journal";
import { reflectionChoices } from "../state/reflection";
import type { PauseResponse } from "../types/api";
import { highlight } from "../utils/highlight";
import pauseL1 from "../fixtures/pause_l1.json";
import pauseL2 from "../fixtures/pause_l2.json";
import pauseL3 from "../fixtures/pause_l3.json";

const en = copyFor("en");
const hi = copyFor("hi");
const asPause = (value: unknown) => value as PauseResponse;
const NOW = new Date("2026-10-04T12:00:00Z");

beforeEach(() => window.localStorage.clear());

describe("highlight (the user's own words, marked in their own message)", () => {
  const message = "Hello.  Guaranteed 3x   return in 7 days. Join our Telegram group, act today!";

  it("marks each quote, ignoring case and runs of whitespace", () => {
    const segments = highlight(message, ["guaranteed 3x return in 7 days.", "Join our Telegram group, act today!"]);
    expect(segments.filter((s) => s.marked).map((s) => s.text)).toEqual([
      "Guaranteed 3x   return in 7 days.",
      "Join our Telegram group, act today!",
    ]);
    expect(segments.map((s) => s.text).join("")).toBe(message);
  });

  it("skips a quote it cannot find (contact details were replaced by placeholders)", () => {
    const segments = highlight("Pay 5000 to rahul@ybl", ["Pay [UPI_USER]@ybl now"]);
    expect(segments).toEqual([{ text: "Pay 5000 to rahul@ybl", marked: false }]);
  });

  it("merges overlapping marks and handles a trailing ellipsis", () => {
    const segments = highlight("act now to get guaranteed returns today", ["act now to get guaranteed", "get guaranteed returns today…"]);
    expect(segments.filter((s) => s.marked)).toEqual([
      { text: "act now to get guaranteed returns today", marked: true },
    ]);
  });

  it("treats regular-expression characters in a quote as plain text", () => {
    const segments = highlight("Earn 3x (guaranteed) [now]? yes", ["(guaranteed) [now]?"]);
    expect(segments.find((s) => s.marked)?.text).toBe("(guaranteed) [now]?");
  });

  it("no quotes means the message is returned whole and unmarked", () => {
    expect(highlight(message, [])).toEqual([{ text: message, marked: false }]);
    expect(highlight("", ["x"])).toEqual([{ text: "", marked: false }]);
  });
});

describe("reflection choices follow the decision", () => {
  it("a guaranteed pitch from an unknown sender offers those two pulls, then the fixed ones", () => {
    expect(reflectionChoices(asPause(pauseL2), en)).toEqual([
      en.reflectByReason.GUARANTEED_RETURN_CLAIM,
      en.reflectByReason.UNSOLICITED_SOURCE,
      en.reflectFomo,
      en.reflectUnderstand,
      en.reflectOther,
    ]);
  });

  it("something a trusted person suggested offers that instead of fear of missing out", () => {
    const trusted = { ...pauseL2, event: { ...pauseL2.event, source_type: "known_person" } };
    const choices = reflectionChoices(asPause(trusted), en);
    expect(choices).toContain(en.reflectTrusted);
    expect(choices).not.toContain(en.reflectFomo);
  });

  it("never more than two specific reasons, and always ends with 'understand' and 'other'", () => {
    const choices = reflectionChoices(asPause(pauseL3), en);
    expect(choices.length).toBeLessThanOrEqual(5);
    expect(choices.slice(-2)).toEqual([en.reflectUnderstand, en.reflectOther]);
  });

  it("without a pause it falls back to the generic list, and it speaks the user's language", () => {
    expect(reflectionChoices(null, en)).toEqual(en.reflectChoices);
    expect(reflectionChoices(asPause(pauseL2), hi)).toContain(hi.reflectByReason.GUARANTEED_RETURN_CLAIM);
  });
});

describe("pace: what the app learns from how the person uses it", () => {
  it("three skipped reflections among the last five means go straight to deciding", () => {
    expect(paceHints(EMPTY_MEMORY).fastDecide).toBe(false);
    for (const skipped of [true, true]) rememberReflection(skipped);
    expect(paceHints(loadMemory()).fastDecide).toBe(false);
    rememberReflection(true);
    expect(paceHints(loadMemory()).fastDecide).toBe(true);
  });

  it("using the reflection again brings it back", () => {
    for (const skipped of [true, true, true, false, false, false]) rememberReflection(skipped);
    expect(loadMemory().reflectSkipped).toHaveLength(5);
    expect(paceHints(loadMemory()).fastDecide).toBe(false);
  });

  it("remembers the last real funding source and ignores 'unknown'", () => {
    rememberFunding("savings");
    rememberFunding("unknown");
    rememberFunding(undefined);
    expect(loadMemory().lastFunding).toBe("savings");
  });

  it("junk in storage gives an empty memory instead of an error", () => {
    window.localStorage.setItem("ruko.memory.v1", "{not json");
    expect(loadMemory()).toEqual(EMPTY_MEMORY);
    window.localStorage.setItem("ruko.memory.v1", JSON.stringify({ reflectSkipped: "x", waits: 5 }));
    expect(loadMemory().reflectSkipped).toEqual([]);
    expect(loadMemory().waits).toEqual([]);
  });
});

describe("'lately' context is trusted for a day", () => {
  it("is fresh within 24 hours and stale after", () => {
    rememberRecent({ postLoss: true, trades: "6_20" }, NOW);
    const memory = loadMemory();
    expect(freshRecent(memory, new Date(NOW.getTime() + 23 * 3_600_000))).toMatchObject({ postLoss: true });
    expect(freshRecent(memory, new Date(NOW.getTime() + 25 * 3_600_000))).toBeNull();
    expect(freshRecent(memory, new Date(NOW.getTime() - 3_600_000))).toBeNull();
  });

  it("is sent with the request only while fresh, as the person's own declaration", () => {
    rememberRecent({ postLoss: true, trades: "6_20" }, NOW);
    expect(profileForRequest(NOW).recent).toEqual({ post_loss: true, trades_this_week: "6_20" });
    expect(profileForRequest(new Date(NOW.getTime() + 30 * 3_600_000)).recent).toBeUndefined();
  });
});

function wait(over: Partial<Wait> = {}): Wait {
  return {
    id: "w1",
    entryId: "e1",
    createdAt: NOW.toISOString(),
    dueAt: new Date(NOW.getTime() + 3_600_000).toISOString(),
    note: "a tip",
    level: "L2",
    productClass: "scheme_or_app",
    status: "waiting",
    ...over,
  };
}

describe("waits", () => {
  it("the wait is the person's own cooling-off minutes, else one day", () => {
    expect(waitDueAt(15, NOW)).toBe(new Date(NOW.getTime() + 15 * 60_000).toISOString());
    expect(waitDueAt(undefined, NOW)).toBe(new Date(NOW.getTime() + 24 * 3_600_000).toISOString());
    expect(waitDueAt(0, NOW)).toBe(new Date(NOW.getTime() + 24 * 3_600_000).toISOString());
  });

  it("is due once its time has passed, and resolved waits stop appearing", () => {
    addWait(wait());
    expect(isDue(wait(), NOW)).toBe(false);
    expect(isDue(wait(), new Date(NOW.getTime() + 2 * 3_600_000))).toBe(true);
    expect(pendingWaits(loadMemory())).toHaveLength(1);
    resolveWait("w1", "let_go");
    expect(pendingWaits(loadMemory())).toHaveLength(0);
  });

  it("keeps at most 20 and shows the earliest due first", () => {
    for (let i = 0; i < 25; i++) addWait(wait({ id: `w${i}`, dueAt: new Date(NOW.getTime() + i * 1000).toISOString() }));
    const memory = loadMemory();
    expect(memory.waits).toHaveLength(20);
    expect(pendingWaits(memory)[0].dueAt <= pendingWaits(memory)[1].dueAt).toBe(true);
  });
});

function record(over: Partial<JournalRecord["entry"]> = {}): JournalRecord {
  return {
    entry: {
      id: "e1", date: "2026-10-01", stage: "consider_action", product_class: "scheme_or_app",
      source_type: "unknown", level_shown: "L2", reason_codes: [], action: "delayed", overrode: false,
      override_reason_given: false, pause_completed: true, could_state_why: true, followed_own_rules: true,
      ...over,
    },
    notes: { shared_excerpt: "", reflection_choice: null, reflection_text: "" },
  }; // prettier-ignore
}

const memoryWith = (change: Partial<Memory>): Memory => ({ ...EMPTY_MEMORY, ...change });
const RULES = { rules: { max_share_of_savings_pct: 10 } };

describe("home cards: only what the person did or has not yet done", () => {
  it("a quiet new person sees nothing extra", () => {
    expect(homeCards({ memory: EMPTY_MEMORY, journal: [], profile: {}, now: NOW })).toEqual([]);
  });

  it("a due wait comes before one still running, at most two", () => {
    const memory = memoryWith({
      waits: [
        wait({ id: "later", dueAt: new Date(NOW.getTime() + 9e6).toISOString() }),
        wait({ id: "due", dueAt: new Date(NOW.getTime() - 1000).toISOString() }),
        wait({ id: "third", dueAt: new Date(NOW.getTime() + 2e7).toISOString() }),
      ],
    });
    const cards = homeCards({ memory, journal: [], profile: RULES, now: NOW });
    expect(cards).toHaveLength(2);
    expect(cards[0]).toMatchObject({ kind: "wait", due: true });
    expect(cards.every((c) => c.kind === "wait")).toBe(true);
  });

  it("suggestions appear only when nothing is pending, one at a time", () => {
    const journal = [record(), record({ id: "e2" }), record({ id: "e3" })];
    const none = homeCards({ memory: EMPTY_MEMORY, journal, profile: {}, now: NOW });
    expect(none).toEqual([{ kind: "rules" }]);
    const withRules = homeCards({ memory: EMPTY_MEMORY, journal, profile: RULES, now: NOW });
    expect(withRules).toEqual([{ kind: "patterns" }]);
    const pending = homeCards({ memory: memoryWith({ waits: [wait()] }), journal, profile: {}, now: NOW });
    expect(pending.map((c) => c.kind)).toEqual(["wait"]);
  });

  it("a dismissed suggestion stays dismissed", () => {
    dismiss("rules");
    const journal = [record()];
    expect(homeCards({ memory: loadMemory(), journal, profile: {}, now: NOW })).toEqual([]);
  });

  it("the rules nudge needs at least one decision on record; patterns needs three", () => {
    expect(homeCards({ memory: EMPTY_MEMORY, journal: [], profile: {}, now: NOW })).toEqual([]);
    expect(homeCards({ memory: EMPTY_MEMORY, journal: [record(), record({ id: "b" })], profile: RULES, now: NOW })).toEqual([]);
  });

  it("asks about a plan only after a day, once, and not if snoozed", () => {
    const plan = { reason_given: true, horizon: "weeks" as const, reconsider_condition_given: true };
    const old = record({ id: "p1", date: "2026-10-01", plan });
    expect(homeCards({ memory: EMPTY_MEMORY, journal: [old], profile: RULES, now: NOW })[0]).toEqual({
      kind: "plan", entryId: "p1", date: "2026-10-01",
    }); // prettier-ignore
    const fresh = record({ id: "p2", date: "2026-10-04", plan });
    expect(homeCards({ memory: EMPTY_MEMORY, journal: [fresh], profile: RULES, now: NOW })).toEqual([]);
    expect(homeCards({ memory: EMPTY_MEMORY, journal: [old], profile: RULES, now: NOW, snoozed: ["p1"] })).toEqual([]);
    const answered = record({ id: "p3", date: "2026-10-01", plan, plan_followed: true });
    expect(homeCards({ memory: EMPTY_MEMORY, journal: [answered], profile: RULES, now: NOW })).toEqual([]);
  });
});

describe("the decide screen's options fit the decision", () => {
  it("a stronger pause leads with waiting and puts 'go ahead' near the end", () => {
    const options = decisionOptions(asPause(pauseL2));
    expect(options.slice(0, 2)).toEqual(["delayed", "changed_amount"]);
    expect(options.indexOf("went_ahead")).toBeGreaterThan(options.indexOf("dropped"));
  });

  it("a small nudge leads with going ahead, and every option stays available", () => {
    const options = decisionOptions(asPause(pauseL1));
    expect(options[0]).toBe("went_ahead");
    expect(new Set(options)).toEqual(new Set(["went_ahead", "delayed", "changed_amount", "dropped", "set_plan"]));
  });

  it("a decision that lacks a plan offers 'make a plan' first", () => {
    const reasons = pauseL3.decision.reasons.map((r) => r.code);
    expect(reasons).toContain("UNPLANNED_DECISION");
    expect(decisionOptions(asPause(pauseL3))[0]).toBe("set_plan");
  });

  it("with no pause (a bare decision) the plan option comes last", () => {
    const options = decisionOptions(null);
    expect(options[options.length - 1]).toBe("set_plan");
  });
});

describe("the journal records the plan, the person's own rules, and changing the amount", () => {
  const base = { ...initialState, response: pauseL2 as never, action: "went_ahead" as const, overrode: true };

  it("counts their rules and plans and carries which plan parts exist", () => {
    saveProfile({ rules: { max_share_of_savings_pct: 10, no_borrowed_money: true }, emergency_buffer_months: 3, plans: [{ id: "p", product_class: "derivative", amount_min_inr: 1, amount_max_inr: 2 }] });
    const plan = { reason_given: true, horizon: "days" as const, reconsider_condition_given: false };
    const { entry } = buildJournalRecord({ ...base, plan })!;
    expect(entry.plan).toEqual(plan);
    expect(entry.own_rules_count).toBe(3);
    expect(entry.own_plans_count).toBe(1);
  });

  it("going ahead after changing the amount is recorded as reconsidering, not as an override", () => {
    const { entry } = buildJournalRecord({ ...base, changedAmount: true })!;
    expect(entry.action).toBe("changed_amount");
    expect(entry.overrode).toBe(false);
    expect(entry.override_reason_given).toBe(false);
  });

  it("without a plan the entry carries none", () => {
    expect(buildJournalRecord(base)!.entry.plan).toBeUndefined();
  });

  it("counts own rules the same way the form writes them", () => {
    expect(ownRulesCount({})).toBe(0);
    expect(ownRulesCount({ rules: { protected_goals: [{ id: "g", amount_inr: 5 }] } })).toBe(1);
    expect(ownRulesCount({ rules: { no_borrowed_money: false } })).toBe(0);
    expect(loadProfile()).toBeDefined();
  });
});
