"use client";

import { ThemeToggle } from "@/components/ThemeToggle";
import { useUser } from "@/components/AppShell";
import { useT } from "@/lib/useT";

type Kind = "today" | "history" | "historyDay" | "progress" | "profile";

/** Stand-in for a screen that ticket 06 builds. It lives inside the real shell so the
 *  frame, navigation and sign-in guard can be exercised already. */
export function ScreenPlaceholder({ kind, detail }: { kind: Kind; detail?: string }) {
  const { t } = useT();
  const { user, signOut } = useUser();
  const title = kind === "historyDay" ? t.nav.history : t.nav[kind];

  return (
    <section className="enter pt-4">
      <h1 className="text-[length:var(--text-base)] font-display">{title}</h1>
      {detail && <p className="label mt-2">{detail}</p>}
      <p className="mt-3 text-dim">{t.placeholder[kind]}</p>

      {kind === "profile" && (
        <div className="mt-8 flex flex-col items-start gap-5">
          <p className="label">{user.email}</p>
          <ThemeToggle />
          <button
            type="button"
            onClick={signOut}
            className="press font-mono text-[length:var(--text-label)] uppercase tracking-[0.16em] text-label transition-colors hover:text-error"
          >
            {t.nav.signOut}
          </button>
        </div>
      )}
    </section>
  );
}
