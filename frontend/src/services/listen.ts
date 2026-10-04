// "Listen": read a screen's text aloud. First choice is Ruko's own voice (/v1/speak, which only
// reads Ruko's pre-written, filtered templates). If that is unavailable, the phone's built-in
// speech is used for the same on-screen text, and the caller is told so it can say so.

import { speak } from "./api";
import type { Locale, TemplateRef } from "../types/api";

export type ListenOutcome = "ruko_voice" | "browser_voice" | "unavailable";

export type ListenSource = { items: TemplateRef[] } | { lessonId: string };

const BROWSER_LANG: Record<Locale, string> = { en: "en-IN", hi: "hi-IN", kn: "kn-IN" };

let current: HTMLAudioElement | null = null;

/** Stop anything that is being read aloud. */
export function stopListening(): void {
  if (current) {
    current.pause();
    current = null;
  }
  if (typeof window !== "undefined" && "speechSynthesis" in window) window.speechSynthesis.cancel();
}

function browserVoice(text: string, locale: Locale): boolean {
  if (typeof window === "undefined" || !("speechSynthesis" in window) || !text.trim()) return false;
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = BROWSER_LANG[locale];
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(utterance);
  return true;
}

/**
 * Read something aloud.
 *
 * @param locale Language to speak.
 * @param source Template references from a response, or one lesson ID.
 * @param fallbackText The same text as shown on screen, for the phone's own voice.
 * @returns Which voice was used, or "unavailable" if neither worked.
 */
export async function listen(
  locale: Locale,
  source: ListenSource,
  fallbackText: string,
): Promise<ListenOutcome> {
  stopListening();
  try {
    const speech = await speak(locale, source);
    const audio = new Audio(`data:audio/${speech.audio_format};base64,${speech.audio_base64}`);
    current = audio;
    await audio.play();
    return "ruko_voice";
  } catch {
    return browserVoice(fallbackText, locale) ? "browser_voice" : "unavailable";
  }
}
