// PWA: the manifest, the registration module and the service worker's actual behaviour.
// The worker file is plain JavaScript, so the tests run its source against small stand-ins for
// the browser's cache and fetch and check what it answers, never just that strings exist.

import { describe, expect, it, vi } from "vitest";
import indexHtml from "../../index.html?raw";
import manifestText from "../../public/manifest.webmanifest?raw";
import swSource from "../../public/sw.js?raw";
import { registerServiceWorker } from "../pwa/register";

const manifest = JSON.parse(manifestText);

describe("manifest", () => {
  it("is installable: name, standalone, start URL, scope and two PNG icons", () => {
    expect(manifest.name).toBe("Ruko");
    expect(manifest.display).toBe("standalone");
    expect(manifest.start_url).toBe("/");
    expect(manifest.scope).toBe("/");
    const sizes = manifest.icons.map((icon: { sizes: string }) => icon.sizes);
    expect(sizes).toEqual(expect.arrayContaining(["192x192", "512x512"]));
    for (const icon of manifest.icons) {
      expect(icon.type).toBe("image/png");
      expect(icon.src.startsWith("/")).toBe(true);
    }
  });

  it("accepts shared text, titles and links through a GET share target", () => {
    expect(manifest.share_target).toEqual({
      action: "/",
      method: "GET",
      params: { title: "title", text: "text", url: "url" },
    });
  });

  it("is linked from the page, which leaves registration to the app (no inline script)", () => {
    expect(indexHtml).toContain('<link rel="manifest" href="/manifest.webmanifest" />');
    expect(indexHtml).not.toContain("serviceWorker");
  });
});

describe("registerServiceWorker", () => {
  it("registers /sw.js when the browser supports workers", async () => {
    const register = vi.fn().mockResolvedValue({});
    expect(await registerServiceWorker({ serviceWorker: { register } })).toBe(true);
    expect(register).toHaveBeenCalledWith("/sw.js");
  });

  it("does nothing where workers are unsupported, and never throws if registering fails", async () => {
    expect(await registerServiceWorker({})).toBe(false);
    const register = vi.fn().mockRejectedValue(new Error("blocked"));
    expect(await registerServiceWorker({ serviceWorker: { register } })).toBe(false);
  });
});

// --- The service worker --------------------------------------------------------------------

type Listener = (event: unknown) => void;

function loadWorker(online: boolean, existing: Record<string, Map<string, Response>> = {}) {
  const listeners: Record<string, Listener> = {};
  const stores = new Map<string, Map<string, Response>>(Object.entries(existing));
  const cachedKey = (request: Request | string) => (typeof request === "string" ? request : new URL(request.url).pathname);
  const caches = {
    open: async (name: string) => {
      if (!stores.has(name)) stores.set(name, new Map());
      const store = stores.get(name)!;
      return {
        addAll: async (paths: string[]) => paths.forEach((p) => store.set(p, new Response("shell"))),
        put: async (request: Request | string, response: Response) => void store.set(cachedKey(request), response),
      };
    },
    match: async (request: Request | string) => {
      for (const store of stores.values()) {
        const hit = store.get(cachedKey(request));
        if (hit) return hit.clone();
      }
      return undefined;
    },
    keys: async () => [...stores.keys()],
    delete: async (name: string) => stores.delete(name),
  };
  const fetchMock = vi.fn(async (request: Request) => {
    if (!online) throw new TypeError("offline");
    return new Response(`network:${new URL(request.url).pathname}`, { status: 200 });
  });
  const self = {
    addEventListener: (type: string, fn: Listener) => void (listeners[type] = fn),
    location: { origin: "https://ruko.test" },
    skipWaiting: vi.fn(),
    clients: { claim: vi.fn(async () => undefined) },
  };
  new Function("self", "caches", "fetch", "Response", "URL", swSource)(
    self,
    caches,
    fetchMock,
    Response,
    URL,
  );

  /** Fire a fetch event; returns the response promise if the worker answered, else null. */
  async function request(url: string, init: { method?: string; mode?: string } = {}) {
    let answer: Promise<Response> | null = null;
    listeners.fetch({
      request: { url, method: init.method ?? "GET", mode: init.mode ?? "no-cors" },
      respondWith: (promise: Promise<Response>) => void (answer = promise),
    });
    return answer ? (answer as Promise<Response>) : null;
  }
  return { listeners, stores, fetchMock, request, self };
}

const ORIGIN = "https://ruko.test";

describe("service worker", () => {
  it("caches the shell on install", async () => {
    const worker = loadWorker(true);
    let pending: Promise<unknown> = Promise.resolve();
    worker.listeners.install({ waitUntil: (p: Promise<unknown>) => void (pending = p) });
    await pending;
    expect([...worker.stores.get("ruko-shell-v2")!.keys()]).toEqual(["/", "/manifest.webmanifest"]);
    expect(worker.self.skipWaiting).toHaveBeenCalled();
  });

  it("removes old Ruko caches on activate and leaves other sites' caches alone", async () => {
    const worker = loadWorker(true, {
      "ruko-v1": new Map(),
      "ruko-shell-v2": new Map(),
      "someone-else": new Map(),
    });
    let pending: Promise<unknown> = Promise.resolve();
    worker.listeners.activate({ waitUntil: (p: Promise<unknown>) => void (pending = p) });
    await pending;
    expect([...worker.stores.keys()].sort()).toEqual(["ruko-shell-v2", "someone-else"]);
    expect(worker.self.clients.claim).toHaveBeenCalled();
  });

  it("never touches API calls, health checks, non-GET or cross-origin requests", async () => {
    const worker = loadWorker(true);
    expect(await worker.request(`${ORIGIN}/v1/analyze`)).toBeNull();
    expect(await worker.request(`${ORIGIN}/v1/analyze`, { method: "POST" })).toBeNull();
    expect(await worker.request(`${ORIGIN}/health`)).toBeNull();
    expect(await worker.request(`${ORIGIN}/assets/app.js`, { method: "POST" })).toBeNull();
    expect(await worker.request("https://elsewhere.test/lib.js")).toBeNull();
    expect(worker.fetchMock).not.toHaveBeenCalled();
  });

  it("loads pages from the network when online, and keeps the page for offline use", async () => {
    const worker = loadWorker(true);
    const response = await worker.request(`${ORIGIN}/`, { mode: "navigate" });
    expect(await (await response!).text()).toBe("network:/");
    await Promise.resolve();
    expect(worker.stores.get("ruko-shell-v2")!.has("/")).toBe(true);
  });

  it("falls back to the cached page when a page load fails offline", async () => {
    const worker = loadWorker(false, { "ruko-shell-v2": new Map([["/", new Response("cached shell")]]) });
    const response = await worker.request(`${ORIGIN}/?text=shared`, { mode: "navigate" });
    expect(await (await response!).text()).toBe("cached shell");
  });

  it("serves built files from the cache, and caches nothing from the API", async () => {
    const online = loadWorker(true);
    await (await online.request(`${ORIGIN}/assets/app-1.js`))!;
    await Promise.resolve();
    expect(online.stores.get("ruko-shell-v2")!.has("/assets/app-1.js")).toBe(true);
    for (const key of online.stores.get("ruko-shell-v2")!.keys()) {
      expect(key.startsWith("/v1/")).toBe(false);
    }
    const offline = loadWorker(false, {
      "ruko-shell-v2": new Map([["/assets/app-1.js", new Response("cached js")]]),
    });
    expect(await (await offline.request(`${ORIGIN}/assets/app-1.js`))!.text()).toBe("cached js");
  });
});
