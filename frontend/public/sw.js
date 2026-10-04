// Ruko service worker: an offline shell, nothing more.
//
// - API calls (/v1/*, /health) always go to the network and are never cached: analysis needs a
//   connection, and the app says so when it is offline.
// - Page loads are network-first, so a new release is picked up as soon as the phone is online;
//   the cached page is only the fallback, which keeps rules, journal and checklist usable offline.
// - Built files (hashed JS/CSS, icons) are served from the cache and refreshed in the background.
// - Nothing the user typed or shared is put in the app cache. One exception, by necessity: a
//   screenshot shared from another app arrives as a POST to /share, and the page that opens next
//   cannot receive a file any other way. The worker holds that one image in a separate inbox
//   cache for the moment between the share and the page reading it; the page deletes it at once.
//   Shared text and links are turned back into ordinary /?text=… addresses and never stored.

const CACHE = "ruko-shell-v2";
const SHELL = ["/", "/manifest.webmanifest"];
const SHARE_INBOX = "ruko-share-inbox";
const SHARED_IMAGE = "/shared-image";
const SHARE_FIELDS = ["title", "text", "url"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((names) =>
        Promise.all(names.filter((n) => n.startsWith("ruko-") && n !== CACHE && n !== SHARE_INBOX).map((n) => caches.delete(n))),
      )
      .then(() => self.clients.claim()),
  );
});

/** True for requests this worker may answer: same-origin GETs that are not API calls. */
function isAppFile(request, url) {
  return (
    request.method === "GET" &&
    url.origin === self.location.origin &&
    !url.pathname.startsWith("/v1/") &&
    url.pathname !== "/health"
  );
}

/** A share from another app (the manifest's POST share target): an image, or text and links. */
async function receiveShare(request) {
  const home = (query) => Response.redirect(new URL(`/${query}`, self.location.origin).href, 303);
  try {
    const form = await request.formData();
    const file = form.get("media");
    if (file && typeof file === "object" && typeof file.arrayBuffer === "function" && file.size > 0) {
      const inbox = await caches.open(SHARE_INBOX);
      const body = await file.arrayBuffer();
      await inbox.put(SHARED_IMAGE, new Response(body, { headers: { "content-type": file.type } }));
      return home("?shared=image");
    }
    const params = new URLSearchParams();
    for (const key of SHARE_FIELDS) {
      const value = form.get(key);
      if (typeof value === "string" && value.trim()) params.set(key, value);
    }
    const query = params.toString();
    return home(query ? `?${query}` : "");
  } catch {
    return home("");
  }
}

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method === "POST" && url.origin === self.location.origin && url.pathname === "/share") {
    event.respondWith(receiveShare(request));
    return;
  }
  if (!isAppFile(request, url)) return;

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response.ok && url.pathname === "/") {
            const copy = response.clone();
            caches.open(CACHE).then((cache) => cache.put("/", copy));
          }
          return response;
        })
        .catch(() => caches.match("/").then((cached) => cached || Response.error())),
    );
    return;
  }

  event.respondWith(
    caches.match(request).then((cached) => {
      const refresh = fetch(request)
        .then((response) => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(CACHE).then((cache) => cache.put(request, copy));
          }
          return response;
        })
        .catch(() => cached || Response.error());
      return cached || refresh;
    }),
  );
});
