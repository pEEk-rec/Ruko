// Minimal service worker: required for the browser to treat the page as an installable app.
// It caches nothing and stores nothing; every request goes to the network.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));
self.addEventListener("fetch", () => {});
