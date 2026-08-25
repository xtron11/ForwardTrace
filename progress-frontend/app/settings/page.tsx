"use client";

import { Shell } from "@/components/Shell";
import { ReminderSettings } from "@/components/Reminders";
import { useT } from "@/lib/useT";

export default function SettingsPage() {
  return (
    <Shell>
      <Settings />
    </Shell>
  );
}

function Settings() {
  const { t } = useT();
  return (
    <div>
      <h1 className="text-[2.1rem]">{t.nav.settings}</h1>
      <div className="mt-8">
        <ReminderSettings />
      </div>
    </div>
  );
}
