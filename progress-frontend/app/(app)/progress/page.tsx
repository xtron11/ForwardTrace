import type { Metadata } from "next";

import { ScreenPlaceholder } from "@/components/ScreenPlaceholder";

export const metadata: Metadata = { title: "Progress" };

export default function ProgressPage() {
  return <ScreenPlaceholder kind="progress" />;
}
