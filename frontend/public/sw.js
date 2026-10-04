// Ruko service worker: an offline shell, nothing more.
//
// - API calls (/v1/*, /health) always go to the network and are never cached: analysis needs a
//   connection, and the app says so when it is offline.
// - Page loads are network-first, so a new release is picked up as soon as the phone is online;
//   the cached page is only the fallback, which keeps rules, journal and checklist usable offline.
// - Built files (hashed JS/CSS, icons) are served from the cache and refreshed in the background.
// - Nothing the user typed or shared is ever put in a cache: only GET responses for app files.

const CACHE = "ruko-shell-v2";
const SHELL = ["/", "/manifest.webmanifest"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((names) =>
        Promise.all(names.filter((n) => n.startsWith("ruko-") && n !== CACHE).map((n) => caches.delete(n))),
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

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);
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
