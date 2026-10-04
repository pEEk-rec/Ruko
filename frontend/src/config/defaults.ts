// The one place that defines first-run defaults. The profile defaults mirror the backend's
// UserProfile (src/ruko/models/profile.py) field for field: "skip, use safe defaults" means
// the user has committed to nothing, and Ruko compares them with nothing it invented.
//
// Safe defaults, on purpose:
// - no rules: the rules are the user's own commitments; Ruko never writes them for the user
// - no amounts or bands: Ruko never guesses the user's money
// - interventions "balanced": the backend decides what appears; "quiet" only trims optional
//   extras on the nudge screen (see PauseCard)

import type { Locale, UserProfile } from "../types/api";

export type InterventionStyle = "quiet" | "balanced";

export interface Settings {
  locale: Locale;
  /** True once the first-run flow was finished or skipped. */
  onboarded: boolean;
  largeText: boolean;
  style: InterventionStyle;
}

export const DEFAULT_SETTINGS: Settings = {
  locale: "en",
  onboarded: false,
  largeText: false,
  style: "balanced",
};

/** The profile a user gets when they skip setup: every backend field left unset. */
export const DEFAULT_PROFILE: UserProfile = {};

export const LOCALES: { value: Locale; label: string }[] = [
  { value: "en", label: "English" },
  { value: "hi", label: "हिन्दी" },
  { value: "kn", label: "ಕನ್ನಡ" },
];

/** Limits that match the backend (src/ruko/config.py), so a recording is never rejected late. */
export const VOICE_LIMITS = {
  maxSeconds: 30,
  maxBytes: 5 * 1024 * 1024,
};

/** Backend card/lesson fading keeps at most this many IDs (models/profile.py). */
export const MAX_SEEN_IDS = 200;
