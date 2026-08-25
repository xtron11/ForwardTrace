/* Service worker.
 *
 * Its only real job is receiving push messages while the site is closed. A page that
 * is not open cannot be notified, so this runs independently of any tab.
 *
 * No offline caching: the app is useless without the API anyway, and a stale cached
 * shell would show someone yesterday's data as though it were today's.
 */

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

// Chrome will not offer to install a PWA without a fetch handler. Pass everything
// straight through - intercepting requests here would only add ways to be wrong.
self.addEventListener("fetch", () => {});

self.addEventListener("push", (event) => {
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch {
    payload = {};
  }

  const title = payload.title || "ForwardTrace";
  event.waitUntil(
    self.registration.showNotification(title, {
      body: payload.body || "",
      icon: "/icons/icon-192.png",
      badge: "/icons/icon-192.png",
      // One reminder replaces the previous one rather than stacking: three unread
      // nudges say nothing the first one did not.
      tag: "daily-reminder",
      renotify: false,
      data: { url: payload.url || "/today" },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = (event.notification.data && event.notification.data.url) || "/today";

  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      // Reuse an open tab if there is one; opening a second copy of the app is
      // disorienting when someone already had it open.
      for (const client of clients) {
        if ("focus" in client) {
          client.navigate(target);
          return client.focus();
        }
      }
      return self.clients.openWindow(target);
    }),
  );
});
