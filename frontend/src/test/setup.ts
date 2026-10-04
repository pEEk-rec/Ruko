import "@testing-library/react";
import { beforeEach, vi } from "vitest";

// Tests must not depend on the time of day: the clock says "daytime" unless a test says otherwise.
vi.mock("../services/clock", () => ({
  isLateNight: vi.fn(() => false),
  LATE_NIGHT_FROM_HOUR: 23,
  LATE_NIGHT_BEFORE_HOUR: 5,
}));

beforeEach(() => {
  window.localStorage.clear();
  window.localStorage.setItem(
    "ruko.settings.v1",
    JSON.stringify({ onboarded: true, locale: "en", largeText: false, style: "balanced" })
  );
});
