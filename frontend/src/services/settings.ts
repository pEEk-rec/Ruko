// Device-only settings (language, text size, intervention style, first-run flag).
// Storage can be unavailable; every access is wrapped and falls back to the defaults.

import { DEFAULT_SETTINGS, LOCALES, type Settings } from "../config/defaults";

const KEY = "ruko.settings.v1";

function isLocale(value: unknown): value is Settings["locale"] {
  return LOCALES.some((l) => l.value === value);
}

/** Load settings, ignoring anything unexpected in storage. */
export function loadSettings(): Settings {
  try {
    const raw = window.localStorage.getItem(KEY);
    const stored = raw ? (JSON.parse(raw) as Partial<Settings>) : {};
    return {
      locale: isLocale(stored.locale) ? stored.locale : DEFAULT_SETTINGS.locale,
      onboarded: stored.onboarded === true,
      largeText: stored.largeText === true,
      style: stored.style === "quiet" ? "quiet" : "balanced",
    };
  } catch {
    return { ...DEFAULT_SETTINGS };
  }
}

/** Save settings. Returns false if the device refused storage. */
export function saveSettings(settings: Settings): boolean {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(settings));
    return true;
  } catch {
    return false;
  }
}
