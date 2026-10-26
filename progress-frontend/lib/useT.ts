"use client";

import { useCallback, useSyncExternalStore } from "react";

import { detectLocale, dict, type Locale } from "./i18n";

/**
 * The interface language: `users.locale` once signed in (AppShell calls setLocale with
 * it), the browser's language before that. The last choice is remembered in
 * localStorage so the login screen and the first frame after a reload already match.
 *
 * It is an external store read with useSyncExternalStore: the server snapshot is "en",
 * so hydration agrees with the server, and the real locale follows right after mount.
 */
const KEY = "forwardtrace.locale";

let current: Locale | null = null;
const listeners = new Set<() => void>();

function read(): Locale {
  if (current) return current;
  let stored: string | null = null;
  try {
    stored = window.localStorage.getItem(KEY);
  } catch {
    /* storage blocked: fall back to the browser language */
  }
  current = stored === "ru" || stored === "en" ? stored : detectLocale();
  document.documentElement.lang = current;
  return current;
}

export function setLocale(next: Locale): void {
  if (next === current) return;
  current = next;
  try {
    window.localStorage.setItem(KEY, next);
  } catch {
    /* the choice just will not persist */
  }
  document.documentElement.lang = next;
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useT() {
  const locale = useSyncExternalStore<Locale>(subscribe, read, () => "en");
  const set = useCallback((next: Locale) => setLocale(next), []);
  return { t: dict(locale), locale, setLocale: set };
}
