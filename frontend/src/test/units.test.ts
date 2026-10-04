// Pure logic: number formatting, copy completeness, attention counts, the anonymised summary,
// recorder helpers and the feeling-prompt rule.

import { describe, expect, it } from "vitest";
import { DEFAULT_PROFILE, DEFAULT_SETTINGS } from "../config/defaults";
import { copyFor, flattenCopy, hasDraftStrings, stringStatus } from "../copy";
import { loadSettings, saveSettings } from "../services/settings";
import { formatForMime } from "../services/recorder";
import { attentionFromJournal } from "../services/profile";
import type { JournalRecord } from "../services/device";
import { buildSummary, currentSummaryJson } from "../services/summary";
import { shouldAskFeeling } from "../state/journal";
import { formatInr, groupIndian } from "../utils/format";
import { addJournalRecord, saveEvidence } from "../services/device";

function record(over: Partial<JournalRecord["entry"]> = {}, notes: Partial<JournalRecord["notes"]> = {}): JournalRecord {
  return {
    entry: {
      id: "e1",
      date: "2026-10-01",
      stage: "consider_action",
      product_class: "scheme_or_app",
      amount_inr: 123456,
      source_type: "unsolicited_group",
      level_shown: "L2",
      reason_codes: ["UNSOLICITED_SOURCE"],
      action: "delayed",
      overrode: false,
      override_reason_given: false,
      pause_completed: true,
      could_state_why: true,
      followed_own_rules: true,
      ...over,
    },
    notes: {
      shared_excerpt: "SECRET tip text from a group",
      reflection_choice: null,
      reflection_text: "my private reason",
      ...notes,
    },
  };
}

describe("Indian number grouping", () => {
  it("groups the Indian way", () => {
    expect(groupIndian(0)).toBe("0");
    expect(groupIndian(999)).toBe("999");
    expect(groupIndian(1000)).toBe("1,000");
    expect(groupIndian(161695)).toBe("1,61,695");
    expect(groupIndian(12345678)).toBe("1,23,45,678");
    expect(formatInr(-12500)).toBe("-₹12,500");
    expect(formatInr(2500000)).toBe("₹25,00,000");
  });
});

describe("copy", () => {
  const en = flattenCopy(copyFor("en"));

  it("Hindi and Kannada define exactly the same strings as English, none empty", () => {
    for (const locale of ["hi", "kn"] as const) {
      const other = flattenCopy(copyFor(locale));
      expect(Object.keys(other).sort()).toEqual(Object.keys(en).sort());
      for (const [path, text] of Object.entries(other)) expect(text.trim(), `${locale}.${path}`).not.toBe("");
    }
  });

  it("Hindi and Kannada use their own script, not English placeholders", () => {
    const scripts = { hi: /[ऀ-ॿ]/, kn: /[ಀ-೿]/ };
    for (const locale of ["hi", "kn"] as const) {
      const other = flattenCopy(copyFor(locale));
      const english = Object.entries(other).filter(([path, text]) => text === en[path] && /[A-Za-z]{4,}/.test(text));
      // Product names and acronyms such as UPI may match; real sentences must not.
      expect(english.filter(([, text]) => text.split(" ").length > 2)).toEqual([]);
      expect(scripts[locale].test(other.homeTitle)).toBe(true);
    }
  });

  it("every Hindi and Kannada string is a draft until a native speaker verifies it", () => {
    for (const locale of ["hi", "kn"] as const) {
      expect(hasDraftStrings(locale)).toBe(true);
      for (const path of Object.keys(flattenCopy(copyFor(locale)))) {
        expect(stringStatus(locale, path)).toBe("draft");
      }
    }
  });

  it("no locale asserts that an offer is safe, genuine or real", () => {
    const claims = [/(सुरक्षित|असली|भरोसेमंद) (है|हैं)/, /(ಸುರಕ್ಷಿತ|ನಿಜವಾದ|ಅಸಲಿ|ನಂಬಲರ್ಹ) ?(ಆಗಿದೆ|ಇದೆ|ವಾಗಿದೆ)/];
    const hedge = /(नहीं बता सकता|ಹೇಳಲು ಸಾಧ್ಯವಿಲ್ಲ)/;
    for (const locale of ["hi", "kn"] as const) {
      for (const text of Object.values(flattenCopy(copyFor(locale)))) {
        if (hedge.test(text)) continue;
        for (const pattern of claims) expect(text).not.toMatch(pattern);
      }
    }
  });
});

describe("settings and defaults", () => {
  it("the safe defaults set no rules and invent no figures", () => {
    expect(DEFAULT_PROFILE).toEqual({});
    expect(DEFAULT_SETTINGS).toEqual({ locale: "en", onboarded: false, largeText: false, style: "balanced" });
  });

  it("settings round-trip, and junk in storage falls back to the defaults", () => {
    window.localStorage.clear();
    expect(loadSettings()).toEqual(DEFAULT_SETTINGS);
    saveSettings({ locale: "kn", onboarded: true, largeText: true, style: "quiet" });
    expect(loadSettings()).toEqual({ locale: "kn", onboarded: true, largeText: true, style: "quiet" });
    window.localStorage.setItem("ruko.settings.v1", JSON.stringify({ locale: "fr", style: "loud" }));
    expect(loadSettings()).toEqual(DEFAULT_SETTINGS);
    window.localStorage.setItem("ruko.settings.v1", "not json");
    expect(loadSettings()).toEqual(DEFAULT_SETTINGS);
  });
});

describe("attention counts (counted on the device, from the journal)", () => {
  const now = new Date("2026-10-04T10:00:00Z");

  it("counts interventions in the last seven days and the rules-followed streak", () => {
    const records = [
      record({ date: "2026-10-03", level_shown: "L1", followed_own_rules: true }),
      record({ date: "2026-10-02", level_shown: "L2", followed_own_rules: true }),
      record({ date: "2026-09-30", level_shown: "L3", followed_own_rules: false }),
      record({ date: "2026-09-01", level_shown: "L3", followed_own_rules: true }),
    ];
    expect(attentionFromJournal(records, now)).toEqual({
      l1_this_week: 1,
      l2_this_week: 1,
      l3_this_week: 1,
      rule_following_streak: 2,
    });
  });

  it("an empty journal gives zeros", () => {
    expect(attentionFromJournal([], now)).toEqual({
      l1_this_week: 0,
      l2_this_week: 0,
      l3_this_week: 0,
      rule_following_streak: 0,
    });
  });
});

describe("anonymised summary", () => {
  it("counts only: no text, no amounts, no IDs, no entry dates", () => {
    const records = [
      record({}, { cooling_off: { minutes: 15, skipped: true }, feeling: "annoying", origin: "app" }),
      record({ level_shown: "L3", action: "went_ahead", overrode: true, override_reason_given: true }),
      record({ level_shown: "L0", action: "went_ahead", overrode: false, pause_completed: null, could_state_why: null }, { origin: "broker_demo" }),
    ];
    const summary = buildSummary(records, { paid_scammer: [0, 2], cannot_withdraw: [] }, "2026-10-04");
    expect(summary).toMatchObject({
      decisions: 3,
      by_level: { L0: 1, L1: 0, L2: 1, L3: 1 },
      by_action: { went_ahead: 2, delayed: 1, changed_amount: 0, set_plan: 0, dropped: 0 },
      pauses: 2,
      pauses_read_through: 2,
      could_state_why: 2,
      reconsidered_after_pause: 1,
      overrides_with_reason: 1,
      overrides_without_reason: 0,
      cooling_off_offered: 1,
      cooling_off_skipped: 1,
      pause_feeling: { helpful: 0, fine: 0, annoying: 1 },
      from_broker_demo: 1,
      recovery_checklists_started: 1,
      recovery_items_ticked: 2,
    });
    const text = JSON.stringify(summary);
    for (const leak of ["SECRET", "private reason", "123456", "e1", "2026-10-01", "UNSOLICITED", "scheme_or_app"]) {
      expect(text).not.toContain(leak);
    }
    // Every value is a number except the fixed labels.
    const flat = JSON.stringify(summary, (_k, v) => (typeof v === "number" ? 0 : v));
    expect(flat).not.toMatch(/"(?!ruko-anonymised-summary|2026-10-04)[A-Za-z ]{12,}"\s*[,}\]]/);
  });

  it("is built from this phone's journal and evidence ticks", () => {
    window.localStorage.clear();
    addJournalRecord(record());
    saveEvidence("paid_scammer", [1]);
    const parsed = JSON.parse(currentSummaryJson(new Date("2026-10-04T00:00:00Z")));
    expect(parsed.decisions).toBe(1);
    expect(parsed.recovery_items_ticked).toBe(1);
    expect(parsed.generated_on).toBe("2026-10-04");
  });
});

describe("recorder helpers", () => {
  it("maps browser MIME types to the backend's audio formats", () => {
    expect(formatForMime("audio/webm;codecs=opus")).toBe("webm");
    expect(formatForMime("audio/ogg;codecs=opus")).toBe("ogg");
    expect(formatForMime("audio/mp4")).toBe("m4a");
    expect(formatForMime("video/x-unknown")).toBeNull();
  });
});

describe("weekly pause rating", () => {
  const now = new Date("2026-10-04T10:00:00Z");
  it("is offered only after a pause, and at most once a week", () => {
    expect(shouldAskFeeling("L0", [], now)).toBe(false);
    expect(shouldAskFeeling(undefined, [], now)).toBe(false);
    expect(shouldAskFeeling("L2", [], now)).toBe(true);
    expect(shouldAskFeeling("L1", [record({ date: "2026-10-02" }, { feeling: "fine" })], now)).toBe(false);
    expect(shouldAskFeeling("L2", [record({ date: "2026-09-20" }, { feeling: "fine" })], now)).toBe(true);
    expect(shouldAskFeeling("L2", [record({ date: "2026-10-03" })], now)).toBe(true);
  });
});
