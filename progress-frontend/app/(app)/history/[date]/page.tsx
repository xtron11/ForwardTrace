import type { Metadata } from "next";

import { HistoryDayPlaceholder } from "@/components/HistoryDayPlaceholder";

export const metadata: Metadata = { title: "History" };

export default function HistoryDayPage() {
  return <HistoryDayPlaceholder />;
}
