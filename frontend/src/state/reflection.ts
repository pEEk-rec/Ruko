// Picks the reflection choices for this decision: what pulled this person in is different for a
// forwarded "guaranteed" pitch, for something a trusted friend suggested, and for someone who is
// trying to win back a loss. The reasons come from the backend's own decision; the wording is
// frontend text in the user's language. Always ends with "I understand it" and "Something else".

import type { Copy } from "../copy";
import type { PauseResponse } from "../types/api";

const MAX_SPECIFIC = 2;

export function reflectionChoices(pause: PauseResponse | null, t: Copy): string[] {
  if (!pause) return t.reflectChoices;
  const specific: string[] = [];
  for (const reason of pause.decision.reasons) {
    const text = t.reflectByReason[reason.code];
    if (text && !specific.includes(text)) specific.push(text);
    if (specific.length === MAX_SPECIFIC) break;
  }
  const pull = pause.event?.source_type === "known_person" ? t.reflectTrusted : t.reflectFomo;
  return [...specific, pull, t.reflectUnderstand, t.reflectOther];
}
