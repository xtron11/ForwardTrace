/**
 * Installing the app to the home screen.
 *
 * Chrome and the Android browsers fire `beforeinstallprompt` when a site qualifies, and
 * let you defer it. Safari fires nothing at all: on iOS the only route is Share → Add to
 * Home Screen, done by hand, which is also the precondition for notifications there.
 */

import { isStandalone } from "./push";

type InstallEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
};

let deferred: InstallEvent | null = null;
const listeners = new Set<() => void>();

function announce() {
  listeners.forEach((fn) => fn());
}

/** Call once, early. The event fires before any settings screen is mounted, so it has
 *  to be caught at startup or it is lost. */
export function watchForInstallPrompt(): () => void {
  if (typeof window === "undefined") return () => {};

  const onPrompt = (event: Event) => {
    // Stop the browser's own bar so the offer can be made somewhere it makes sense.
    event.preventDefault();
    deferred = event as InstallEvent;
    announce();
  };
  const onInstalled = () => {
    deferred = null;
    announce();
  };

  window.addEventListener("beforeinstallprompt", onPrompt);
  window.addEventListener("appinstalled", onInstalled);
  return () => {
    window.removeEventListener("beforeinstallprompt", onPrompt);
    window.removeEventListener("appinstalled", onInstalled);
  };
}

export function subscribeToInstallState(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export type InstallState =
  | "installed" // already running from the home screen
  | "available" // the browser offered, and we kept the offer
  | "manual" // iOS, or a browser that never offers
  | "unavailable";

export function installState(): InstallState {
  if (typeof window === "undefined") return "unavailable";
  if (isStandalone()) return "installed";
  if (deferred) return "available";

  const ua = navigator.userAgent;
  const iOS =
    /iphone|ipad|ipod/i.test(ua) ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  return iOS ? "manual" : "unavailable";
}

/** Returns true if the person accepted. */
export async function promptInstall(): Promise<boolean> {
  if (!deferred) return false;
  const event = deferred;
  // A deferred prompt is single-use; keeping it around would show a dead button.
  deferred = null;
  await event.prompt();
  const { outcome } = await event.userChoice;
  announce();
  return outcome === "accepted";
}
