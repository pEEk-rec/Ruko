// "Late at night where you are": a clock fact, one yes/no in the profile, never the time itself.

import { describe, expect, it, vi } from "vitest";
import { updateMemory } from "../services/memory";
import { profileForRequest } from "../services/profile";

const actual = await vi.importActual<typeof import("../services/clock")>("../services/clock");
const clock = await import("../services/clock");

describe("the clock rule", () => {
  const at = (hour: number) => new Date(2026, 9, 4, hour, 30);
  it("counts 11 pm until before 5 am as late at night", () => {
    expect([22, 23, 0, 3, 4].map((h) => actual.isLateNight(at(h)))).toEqual([false, true, true, true, true]);
    expect([5, 9, 15, 20].map((h) => actual.isLateNight(at(h)))).toEqual([false, false, false, false]);
  });
});

describe("what is sent", () => {
  it("sends only a yes/no, merged with what the person declared lately", () => {
    vi.mocked(clock.isLateNight).mockReturnValueOnce(true);
    updateMemory((m) => ({ ...m, recent: { postLoss: true, trades: "1_5", at: new Date().toISOString() } }));
    const profile = profileForRequest();
    expect(profile.recent).toEqual({ post_loss: true, trades_this_week: "1_5", late_night: true });
    expect(JSON.stringify(profile)).not.toMatch(/\d{2}:\d{2}/);
  });

  it("sends nothing about the clock in the daytime", () => {
    expect(profileForRequest().recent).toBeUndefined();
  });

  it("works with no declared context at all", () => {
    vi.mocked(clock.isLateNight).mockReturnValueOnce(true);
    expect(profileForRequest().recent).toEqual({ late_night: true });
  });
});
