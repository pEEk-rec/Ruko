// Find the user's own quoted words inside their own message, so the message can be shown with
// what Ruko noticed marked. Pure text matching on the device; nothing here is sent anywhere.

export interface Segment {
  text: string;
  marked: boolean;
}

function escape(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * Split `text` into segments, marking every place one of the `quotes` occurs.
 * Matching ignores case and treats any run of whitespace as one space. A quote that cannot be
 * found (for example because contact details in it were replaced by placeholders) is skipped.
 */
export function highlight(text: string, quotes: string[]): Segment[] {
  const ranges: [number, number][] = [];
  for (const quote of quotes) {
    const words = quote.replace(/…$/, "").trim().split(/\s+/).filter(Boolean);
    if (words.length === 0) continue;
    const match = new RegExp(words.map(escape).join("\\s+"), "i").exec(text);
    if (match) ranges.push([match.index, match.index + match[0].length]);
  }
  ranges.sort((a, b) => a[0] - b[0]);
  const merged: [number, number][] = [];
  for (const range of ranges) {
    const last = merged[merged.length - 1];
    if (last && range[0] <= last[1]) last[1] = Math.max(last[1], range[1]);
    else merged.push([...range]);
  }
  const segments: Segment[] = [];
  let at = 0;
  for (const [start, end] of merged) {
    if (start > at) segments.push({ text: text.slice(at, start), marked: false });
    segments.push({ text: text.slice(start, end), marked: true });
    at = end;
  }
  if (at < text.length) segments.push({ text: text.slice(at), marked: false });
  return segments.length > 0 ? segments : [{ text, marked: false }];
}
