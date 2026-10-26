import type { Metadata } from "next";

import { DayScreen } from "@/components/DayScreen";
import { PageTitle } from "@/app/PageTitle";
import { dict } from "@/lib/i18n";

export const metadata: Metadata = { title: dict("en").pageTitles.history };

export default function HistoryDayPage() {
  return (
    <>
      <PageTitle page="history" />
      <DayScreen />
    </>
  );
}
