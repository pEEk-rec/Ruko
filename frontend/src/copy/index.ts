// Frontend chrome text for each locale, plus the review status of every string.
// Hindi and Kannada are drafts: nothing is marked human-verified until a native speaker
// has reviewed it (add the string's path to VERIFIED, for example "hi.home").

import type { Locale } from "../types/api";
import { en, type Copy } from "./en";
import { hi } from "./hi";
import { kn } from "./kn";

export type { Copy };

const copies: Record<Locale, Copy> = { en, hi, kn };

/** Frontend chrome text for a locale (falls back to English for an unknown locale). */
export function copyFor(locale: Locale): Copy {
  return copies[locale] ?? en;
}

export type StringStatus = "draft" | "human_verified";

/** Paths of strings a native speaker has verified, per locale. Empty until a review happens. */
export const VERIFIED: Record<Locale, string[]> = { en: [], hi: [], kn: [] };

/** Flatten a copy object to "path" -> string (functions are called with sample arguments). */
export function flattenCopy(value: unknown, path = ""): Record<string, string> {
  if (typeof value === "string") return { [path]: value };
  if (typeof value === "function") {
    return { [path]: String((value as (...args: unknown[]) => unknown)(7, 30)) };
  }
  if (value && typeof value === "object") {
    return Object.entries(value).reduce<Record<string, string>>(
      (all, [key, child]) => ({ ...all, ...flattenCopy(child, path ? `${path}.${key}` : key) }),
      {},
    );
  }
  return {};
}

/** Review status of one string: draft unless a native speaker verified it. */
export function stringStatus(locale: Locale, path: string): StringStatus {
  return VERIFIED[locale].includes(path) ? "human_verified" : "draft";
}

/** True if any string in this locale is still a draft (the settings screen says so). */
export function hasDraftStrings(locale: Locale): boolean {
  return Object.keys(flattenCopy(copyFor(locale))).some(
    (path) => stringStatus(locale, path) === "draft",
  );
}
