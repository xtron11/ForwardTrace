import type { Metadata } from "next";

import { PageTitle } from "@/app/PageTitle";
import { dict } from "@/lib/i18n";

export const metadata: Metadata = { title: dict("en").pageTitles.signIn };

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <PageTitle page="signIn" />
      {children}
    </>
  );
}
