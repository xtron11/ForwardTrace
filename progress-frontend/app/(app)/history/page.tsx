import type { Metadata } from "next";

import { HistoryScreen } from "@/components/HistoryScreen";
import { PageTitle } from "@/app/PageTitle";
import { dict } from "@/lib/i18n";

export const metadata: Metadata = { title: dict("en").pageTitles.history };

export default function HistoryPage() {
  return (
    <>
      <PageTitle page="history" />
      <HistoryScreen />
    </>
  );
}
