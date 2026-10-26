import type { Metadata } from "next";

import { PageTitle } from "@/app/PageTitle";
import { dict } from "@/lib/i18n";

/** Reached only from a letter, with a token: without one a crawler would see nothing
 *  but a broken-link screen. */
export const metadata: Metadata = {
  title: dict("en").pageTitles.restore,
  robots: { index: false, follow: false },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <PageTitle page="restore" />
      {children}
    </>
  );
}
