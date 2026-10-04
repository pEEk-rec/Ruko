// Share-target boundary. When Ruko is installed as a PWA, Android's share sheet opens
// "/?title=…&text=…&url=…" (see public/manifest.webmanifest). This module turns those
// parameters into a RawInput and removes them from the address bar. It is isolated from
// the decision flow: the flow only ever receives a RawInput.

import type { RawInput } from "../types/api";

const MAX_LENGTH = 8000;

/** Read shared content from a URL query string. Returns null if nothing was shared. */
export function readSharedContent(search: string): RawInput | null {
  const params = new URLSearchParams(search);
  const parts = ["title", "text", "url"]
    .map((key) => params.get(key)?.trim() ?? "")
    .filter((value, index, all) => value !== "" && all.indexOf(value) === index);
  if (parts.length === 0) return null;
  const content = parts.join("\n").slice(0, MAX_LENGTH);
  const onlyUrl = parts.length === 1 && params.get("url")?.trim() === content;
  return { type: onlyUrl ? "link" : "text", content };
}

/** Remove share parameters from the address bar so a reload does not resubmit. */
export function clearSharedContent(): void {
  try {
    window.history.replaceState(null, "", window.location.pathname);
  } catch {
    // Not fatal: the worst case is that a reload shows the shared text again.
  }
}
