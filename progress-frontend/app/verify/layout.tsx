import type { Metadata } from "next";

import { PageTitle } from "@/app/PageTitle";
import { dict } from "@/lib/i18n";

/** Behind a sign-in: a crawler would only ever see an empty shell, and an empty shell
 *  in search results teaches the engine the site is thin. */
export const metadata: Metadata = {
  title: dict("en").pageTitles.verify,
  robots: { index: false, follow: false },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <PageTitle page="verify" />
      {children}
    </>
  );
}
