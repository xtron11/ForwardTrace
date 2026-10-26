import type { Metadata } from "next";

import { ProfileScreen } from "@/components/ProfileScreen";
import { PageTitle } from "@/app/PageTitle";
import { dict } from "@/lib/i18n";

export const metadata: Metadata = { title: dict("en").pageTitles.profile };

export default function ProfilePage() {
  return (
    <>
      <PageTitle page="profile" />
      <ProfileScreen />
    </>
  );
}
