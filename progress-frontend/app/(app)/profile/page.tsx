import type { Metadata } from "next";

import { ScreenPlaceholder } from "@/components/ScreenPlaceholder";

export const metadata: Metadata = { title: "Profile" };

export default function ProfilePage() {
  return <ScreenPlaceholder kind="profile" />;
}
