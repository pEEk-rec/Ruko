// Finding the backend's glossary words inside a text. Pure and tiny: it only locates words the
// backend already named (`match`), so it cannot invent a term or an explanation.

import type { TermHit } from "../types/api";

export interface TextPart {
  text: string;
  /** The term this part is a word of, or null for ordinary text. */
  term: TermHit | null;
}

/** At most this many words per text are made tappable (more is noise, not help). */
export const MAX_PER_TEXT = 3;

/**
 * Split a text into ordinary parts and tappable words. Each term is tapped at its first
 * occurrence only; longer wordings win over shorter ones; words never overlap.
 */
export function splitByTerms(
  text: string,
  terms: TermHit[],
  /** Terms already tapped earlier on the screen (a lesson taps each word once, not per paragraph). */
  alreadyTapped: ReadonlySet<string> = new Set(),
): TextPart[] {
  if (!text || terms.length === 0) return [{ text, term: null }];
  const found: { start: number; end: number; term: TermHit }[] = [];
  const usedIds = new Set<string>(alreadyTapped);
  for (const term of [...terms].sort((a, b) => b.match.length - a.match.length)) {
    if (usedIds.has(term.id) || !term.match) continue;
    const start = text.indexOf(term.match);
    if (start < 0) continue;
    const end = start + term.match.length;
    if (found.some((f) => start < f.end && end > f.start)) continue;
    found.push({ start, end, term });
    usedIds.add(term.id);
  }
  const chosen = found.sort((a, b) => a.start - b.start).slice(0, MAX_PER_TEXT);
  if (chosen.length === 0) return [{ text, term: null }];
  const parts: TextPart[] = [];
  let cursor = 0;
  for (const { start, end, term } of chosen) {
    if (start > cursor) parts.push({ text: text.slice(cursor, start), term: null });
    parts.push({ text: text.slice(start, end), term });
    cursor = end;
  }
  if (cursor < text.length) parts.push({ text: text.slice(cursor), term: null });
  return parts;
}
