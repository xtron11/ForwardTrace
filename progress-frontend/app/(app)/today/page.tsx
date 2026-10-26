import type { Metadata } from "next";

import { ScreenPlaceholder } from "@/components/ScreenPlaceholder";

export const metadata: Metadata = { title: "Today" };

export default function TodayPage() {
  return <ScreenPlaceholder kind="today" />;
}
