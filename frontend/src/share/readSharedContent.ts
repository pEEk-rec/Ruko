// Share-target boundary. When Ruko is installed as a PWA, Android's share sheet posts to /share
// (see public/manifest.webmanifest); the service worker turns text and links into
// "/?title=…&text=…&url=…" and a screenshot into "/?shared=image" (the image waits in a
// short-lived inbox cache). This module turns either into a RawInput and clears the address bar. It is isolated from
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
    // A share can land on /share (the server fallback); the app itself lives at "/".
    const path = window.location.pathname === "/share" ? "/" : window.location.pathname;
    window.history.replaceState(null, "", path);
  } catch {
    // Not fatal: the worst case is that a reload shows the shared text again.
  }
}

/** Kept in step with public/sw.js. */
export const SHARE_INBOX = "ruko-share-inbox";
export const SHARED_IMAGE_KEY = "/shared-image";
export const MAX_IMAGE_BYTES = 4_000_000;
export const IMAGE_TYPES = ["image/png", "image/jpeg", "image/webp"];

/** True if the service worker says a screenshot was shared into Ruko. */
export function isSharedImage(search: string): boolean {
  return new URLSearchParams(search).get("shared") === "image";
}

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",")[1] ?? "");
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

/**
 * Take the shared screenshot out of the inbox (it is deleted whatever happens next).
 * Returns the image as base64, "unsupported" for a wrong type or size, or null if none is there.
 */
export async function takeSharedImage(
  store: CacheStorage | undefined = globalThis.caches,
): Promise<RawInput | "unsupported" | null> {
  if (!store) return null;
  try {
    const inbox = await store.open(SHARE_INBOX);
    const response = await inbox.match(SHARED_IMAGE_KEY);
    await inbox.delete(SHARED_IMAGE_KEY);
    if (!response) return null;
    const blob = await response.blob();
    const type = response.headers.get("content-type") ?? blob.type;
    if (!IMAGE_TYPES.includes(type) || blob.size === 0 || blob.size > MAX_IMAGE_BYTES) {
      return "unsupported";
    }
    return { type: "image", content: await blobToBase64(blob) };
  } catch {
    return null;
  }
}

/** Kept in step with src/ruko/api/share.py. */
export const SHARE_DATA_BLOCK_ID = "ruko-shared";

/**
 * A share the server handed back inside the page (when the service worker could not take it):
 * an inert JSON block. Read once, removed at once. Returns null if there is none.
 */
export function takeInlineShare(doc: Document = document): RawInput | "unsupported" | null {
  const block = doc.getElementById(SHARE_DATA_BLOCK_ID);
  if (!block) return null;
  block.remove();
  try {
    const data = JSON.parse(block.textContent ?? "") as Record<string, string>;
    if (data.unsupported) return "unsupported";
    if (data.image) return { type: "image", content: data.image };
    const params = new URLSearchParams();
    for (const key of ["title", "text", "url"]) if (data[key]) params.set(key, data[key]);
    return readSharedContent(`?${params.toString()}`);
  } catch {
    return null;
  }
}
