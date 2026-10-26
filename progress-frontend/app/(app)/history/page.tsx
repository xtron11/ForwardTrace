import type { Metadata } from "next";

import { ScreenPlaceholder } from "@/components/ScreenPlaceholder";

export const metadata: Metadata = { title: "History" };

export default function HistoryPage() {
  return <ScreenPlaceholder kind="history" />;
}
