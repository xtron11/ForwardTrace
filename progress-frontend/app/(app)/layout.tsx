import { AppShell } from "@/components/AppShell";

/** Route group: every signed-in screen shares one AppShell, and the URLs stay as they
 *  are (/today, /history, ...). The shell does the sign-in guard. */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
