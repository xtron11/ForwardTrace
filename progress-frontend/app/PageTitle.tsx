"use client";

import { useEffect } from "react";

import { dict } from "@/lib/i18n";
import { useT } from "@/lib/useT";

export type PageTitleKey = keyof ReturnType<typeof dict>["pageTitles"];

/** The tab title for a page, from the dictionary. The server knows no locale (it lives
 *  in the browser), so the page's metadata title is the English entry
 *  (`dict("en").pageTitles`) and this puts the person's language in once the page is
 *  mounted, and again when the language changes. */
export function PageTitle({ page }: { page: PageTitleKey }) {
  const { t } = useT();
  useEffect(() => {
    document.title = `${t.pageTitles[page]} · ${t.brand}`;
  }, [t, page]);
  return null;
}
