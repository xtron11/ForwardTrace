import type { Metadata } from "next";
import { Suspense } from "react";

import { TodayScreen } from "@/components/TodayScreen";
import { PageTitle } from "@/app/PageTitle";
import { dict } from "@/lib/i18n";

export const metadata: Metadata = { title: dict("en").pageTitles.today };

export default function TodayPage() {
  // TodayScreen reads ?o=<outreach id> from the URL.
  return (
    <>
      <PageTitle page="today" />
      <Suspense fallback={null}>
        <TodayScreen />
      </Suspense>
    </>
  );
}
