import type { Metadata } from "next";
import { Suspense } from "react";

import { TodayScreen } from "@/components/TodayScreen";

export const metadata: Metadata = { title: "Today" };

export default function TodayPage() {
  // TodayScreen reads ?o=<outreach id> from the URL.
  return (
    <Suspense fallback={null}>
      <TodayScreen />
    </Suspense>
  );
}
