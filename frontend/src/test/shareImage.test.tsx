// A screenshot shared from WhatsApp or Telegram: taken once from the inbox, deleted, then checked
// like a screenshot added by hand. Wrong types and sizes get the calm "can't read this" screen.

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import { copyFor } from "../copy";
import { isSharedImage, takeSharedImage } from "../share/readSharedContent";
import clarifyHints from "../fixtures/clarify_hints.json";

const en = copyFor("en");

/** A CacheStorage with one inbox entry (or none). */
function inbox(entry: Response | null) {
  const store = new Map<string, Response>(entry ? [["/shared-image", entry]] : []);
  const cache = {
    match: vi.fn(async (key: string) => store.get(key)),
    delete: vi.fn(async (key: string) => store.delete(key)),
  };
  return { storage: { open: vi.fn(async () => cache) } as unknown as CacheStorage, cache, store };
}
const png = (bytes = 4, type = "image/png") =>
  new Response(new Uint8Array(bytes), { headers: { "content-type": type } });

beforeEach(() => window.history.replaceState(null, "", "/"));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("taking the shared screenshot", () => {
  it("recognises the address the worker opens", () => {
    expect(isSharedImage("?shared=image")).toBe(true);
    expect(isSharedImage("?text=hi")).toBe(false);
  });

  it("returns the image as base64 and deletes it from the inbox", async () => {
    const { storage, store } = inbox(png());
    const taken = await takeSharedImage(storage);
    expect(taken).toEqual({ type: "image", content: "AAAAAA==" });
    expect(store.size).toBe(0);
  });

  it("refuses a type or size Ruko cannot read, and still deletes it", async () => {
    const wrong = inbox(png(4, "image/gif"));
    expect(await takeSharedImage(wrong.storage)).toBe("unsupported");
    expect(wrong.store.size).toBe(0);
    expect(await takeSharedImage(inbox(png(4_000_001)).storage)).toBe("unsupported");
  });

  it("returns nothing when the inbox is empty or storage is unavailable", async () => {
    expect(await takeSharedImage(inbox(null).storage)).toBeNull();
    expect(await takeSharedImage(undefined)).toBeNull();
  });
});

describe("the app", () => {
  it("opens straight into checking a shared screenshot", async () => {
    vi.stubGlobal("caches", inbox(png()).storage);
    const fetchMock = vi.fn(async () => new Response(JSON.stringify(clarifyHints), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    window.history.replaceState(null, "", "/?shared=image");
    render(<App />);
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const body = JSON.parse((fetchMock.mock.calls[0] as unknown as [string, RequestInit])[1].body as string);
    expect(body.input).toEqual({ type: "image", content: "AAAAAA==" });
    expect(window.location.search).toBe("");
  });

  it("shows the calm unsupported screen for an unreadable picture", async () => {
    vi.stubGlobal("caches", inbox(png(4, "image/gif")).storage);
    vi.stubGlobal("fetch", vi.fn());
    window.history.replaceState(null, "", "/?shared=image");
    render(<App />);
    await screen.findByText(en.errors.unsupported_input);
  });
});

describe("a share the server handed back inside the page", () => {
  const block = (data: unknown) => {
    const el = document.createElement("script");
    el.type = "application/json";
    el.id = "ruko-shared";
    el.textContent = JSON.stringify(data);
    document.body.appendChild(el);
  };

  it("takes a photo once and removes the block", async () => {
    const { takeInlineShare } = await import("../share/readSharedContent");
    block({ image: "AAAA" });
    expect(takeInlineShare()).toEqual({ type: "image", content: "AAAA" });
    expect(document.getElementById("ruko-shared")).toBeNull();
    expect(takeInlineShare()).toBeNull();
  });

  it("turns text and links into the same input as any share, and says when a file is unsupported", async () => {
    const { takeInlineShare } = await import("../share/readSharedContent");
    block({ text: "Guaranteed 3x", url: "https://t.me/x" });
    expect(takeInlineShare()).toEqual({ type: "text", content: "Guaranteed 3x\nhttps://t.me/x" });
    block({ unsupported: "1" });
    expect(takeInlineShare()).toBe("unsupported");
  });

  it("the app starts checking a photo handed back by the server", async () => {
    block({ image: "AAAAAA==" });
    const fetchMock = vi.fn(async () => new Response(JSON.stringify(clarifyHints), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    window.history.replaceState(null, "", "/share");
    render(<App />);
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const body = JSON.parse((fetchMock.mock.calls[0] as unknown as [string, RequestInit])[1].body as string);
    expect(body.input).toEqual({ type: "image", content: "AAAAAA==" });
    expect(window.location.pathname).toBe("/");
  });
});
