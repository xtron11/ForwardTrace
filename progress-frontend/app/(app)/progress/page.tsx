import type { Metadata } from "next";

import { ProgressScreen } from "@/components/ProgressScreen";
import { PageTitle } from "@/app/PageTitle";
import { dict } from "@/lib/i18n";

export const metadata: Metadata = { title: dict("en").pageTitles.progress };

export default function ProgressPage() {
  return (
    <>
      <PageTitle page="progress" />
      <ProgressScreen />
    </>
  );
}
