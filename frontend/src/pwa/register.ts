// Registers the offline service worker (public/sw.js). Called only in the production build:
// in development a service worker would serve stale files and fight hot reloading.

interface WorkerHost {
  serviceWorker?: { register: (url: string, options?: { updateViaCache?: "none" }) => Promise<unknown> };
}

/**
 * Register the service worker if the browser supports it.
 *
 * @param host The browser's `navigator` (injectable for tests).
 * @returns True if registration succeeded; false if unsupported or it failed (never throws).
 */
export async function registerServiceWorker(host: WorkerHost = navigator): Promise<boolean> {
  if (!host.serviceWorker) return false;
  try {
    // Always fetch sw.js fresh, so a phone picks up a new worker (for example the share handler)
    // on its next visit instead of keeping an old one.
    await host.serviceWorker.register("/sw.js", { updateViaCache: "none" });
    return true;
  } catch {
    return false;
  }
}
