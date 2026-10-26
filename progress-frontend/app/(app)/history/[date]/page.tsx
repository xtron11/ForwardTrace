import type { Metadata } from "next";

import { DayScreen } from "@/components/DayScreen";

export const metadata: Metadata = { title: "History" };

export default function HistoryDayPage() {
  return <DayScreen />;
}
