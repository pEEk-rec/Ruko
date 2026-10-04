// The frontend's own text must never make the assertions CLAUDE.md forbids (verdicts,
// tips, predictions, "safe"/"legit" claims) or ask for secrets.

import { describe, expect, it } from "vitest";
import { copyFor } from "../copy";

function allStrings(value: unknown): string[] {
  if (typeof value === "string") return [value];
  if (typeof value === "function") return [String((value as (n: number) => string)(15))];
  if (Array.isArray(value)) return value.flatMap(allStrings);
  if (value && typeof value === "object") return Object.values(value).flatMap(allStrings);
  return [];
}

const FORBIDDEN = [
  /\b(is|are|looks?) (safe|legit|genuine|guaranteed|a scam|fake)\b/i,
  /\b(you should|we recommend|buy now|sell now|hold it)\b/i,
  /\b(will (rise|fall|go up|go down))\b/i,
  /\b(enter|share|give|type) (your )?(otp|pin|password|card number|account number|aadhaar|pan)\b/i,
];

// Like the backend's reporting frames: "can't tell whether X is genuine" states uncertainty,
// it does not assert. Only a claim word after an explicit "can't tell ... whether" is allowed.
const HEDGE_FRAME = /\bcan't tell\b[^.]*\bwhether\b/i;

/** True if the forbidden match sits inside a hedge frame. */
function isHedged(text: string, match: RegExpMatchArray): boolean {
  const before = text.slice(0, match.index ?? 0);
  return HEDGE_FRAME.test(before);
}

describe("frontend copy", () => {
  it("contains no forbidden assertion or secret request", () => {
    for (const text of allStrings(copyFor("en"))) {
      for (const pattern of FORBIDDEN) {
        const match = text.match(pattern);
        if (match && pattern === FORBIDDEN[0] && isHedged(text, match)) continue;
        expect(text, text).not.toMatch(pattern);
      }
    }
  });

  it("the hedge frame does not excuse a plain assertion", () => {
    const text = "This offer is genuine.";
    const match = text.match(FORBIDDEN[0])!;
    expect(isHedged(text, match)).toBe(false);
  });
});
