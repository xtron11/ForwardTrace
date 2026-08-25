"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { clearTokens, isSignedIn } from "@/lib/api";
import { useT } from "@/lib/useT";

const TAB_HREFS = ["/today", "/timeline", "/report", "/goals"] as const;

export function Shell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { t } = useT();
  const [ready, setReady] = useState(false);

  const tabs = [
    { href: "/today", label: t.nav.today },
    { href: "/timeline", label: t.nav.timeline },
    { href: "/report", label: t.nav.report },
    { href: "/goals", label: t.nav.goals },
  ];

  useEffect(() => {
    if (!isSignedIn()) router.replace("/login");
    else setReady(true);
  }, [router]);

  if (!ready) {
    return <div className="min-h-dvh bg-paper" aria-hidden />;
  }

  return (
    <div className="min-h-dvh bg-paper">
      <header className="border-b border-rule">
        <div className="mx-auto flex max-w-[680px] items-center justify-between px-5 py-4">
          <Link href="/today" className="font-display text-[17px] font-semibold tracking-tight">
            {t.brand}
          </Link>
          <nav className="flex flex-wrap items-center gap-x-5 gap-y-1">
            {tabs.map((tab) => (
              <Link
                key={tab.href}
                href={tab.href}
                className={`font-mono text-[12px] uppercase tracking-[0.12em] transition-colors ${
                  pathname === tab.href ? "text-ink" : "text-muted hover:text-ink"
                }`}
              >
                {tab.label}
              </Link>
            ))}
            <button
              onClick={() => {
                clearTokens();
                router.replace("/login");
              }}
              className="font-mono text-[12px] uppercase tracking-[0.12em] text-muted hover:text-ink"
            >
              {t.nav.signOut}
            </button>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-[680px] px-5 py-10">{children}</main>
    </div>
  );
}
