"use client";

import { useEffect, useState } from "react";

import { detectLocale, dict, type Locale } from "./i18n";

/**
 * Server and first client render must agree, so start at "en" and switch after mount.
 * Rendering the detected locale during SSR would produce a hydration mismatch, since
 * the server has no access to navigator.language.
 */
export function useT() {
  const [locale, setLocale] = useState<Locale>("en");

  useEffect(() => {
    setLocale(detectLocale());
  }, []);

  return { t: dict(locale), locale };
}
