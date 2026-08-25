"use client";

import { api } from "./api";

/** VAPID keys travel as URL-safe base64; the browser wants raw bytes. */
function urlBase64ToUint8Array(base64: string): Uint8Array {
  const padded = (base64 + "=".repeat((4 - (base64.length % 4)) % 4))
    .replace(/-/g, "+")
    .replace(/_/g, "/");
  const raw = atob(padded);
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
}

export type PushState =
  | "unsupported"
  | "unconfigured"
  | "needs-install" // iOS: notifications only work once added to the home screen
  | "denied"
  | "off"
  | "on";

export function isStandalone(): boolean {
  if (typeof window === "undefined") return false;
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    // Safari's non-standard flag, still the only reliable signal on iOS.
    (window.navigator as unknown as { standalone?: boolean }).standalone === true
  );
}

function isIOS(): boolean {
  if (typeof navigator === "undefined") return false;
  return /iPad|iPhone|iPod/.test(navigator.userAgent);
}

export async function pushState(): Promise<PushState> {
  if (typeof window === "undefined") return "unsupported";
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
    // On iOS this is what an un-installed site looks like: the APIs simply are not
    // there until the person adds it to the home screen.
    return isIOS() && !isStandalone() ? "needs-install" : "unsupported";
  }

  const { enabled } = await api.pushKey().catch(() => ({ enabled: false, key: "" }));
  if (!enabled) return "unconfigured";

  if (Notification.permission === "denied") return "denied";

  const registration = await navigator.serviceWorker.getRegistration();
  const existing = await registration?.pushManager.getSubscription();
  return existing ? "on" : "off";
}

export async function enablePush(): Promise<PushState> {
  const { key, enabled } = await api.pushKey();
  if (!enabled || !key) return "unconfigured";

  const registration = await navigator.serviceWorker.register("/sw.js");
  await navigator.serviceWorker.ready;

  // Must follow a user gesture, or the browser rejects it outright.
  const permission = await Notification.requestPermission();
  if (permission !== "granted") return permission === "denied" ? "denied" : "off";

  const subscription =
    (await registration.pushManager.getSubscription()) ??
    (await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(key),
    }));

  const raw = subscription.toJSON() as {
    endpoint?: string;
    keys?: { p256dh?: string; auth?: string };
  };
  if (!raw.endpoint || !raw.keys?.p256dh || !raw.keys?.auth) return "off";

  await api.pushSubscribe({
    endpoint: raw.endpoint,
    keys: { p256dh: raw.keys.p256dh, auth: raw.keys.auth },
  });
  return "on";
}

export async function disablePush(): Promise<PushState> {
  const registration = await navigator.serviceWorker.getRegistration();
  const subscription = await registration?.pushManager.getSubscription();
  if (subscription) {
    await api.pushUnsubscribe(subscription.endpoint).catch(() => {});
    await subscription.unsubscribe();
  }
  return "off";
}
