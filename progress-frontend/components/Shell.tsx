"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { isSignedIn } from "@/lib/api";
import { activeRegistration } from "@/lib/push";
import { watchForInstallPrompt } from "@/lib/pwa";
import { useT } from "@/lib/useT";

/**
 * Four destinations, no more. Settings sits behind the gear on Today and signing out
 * sits inside settings: both are rare, and six tabs do not fit a phone.
 */
const TABS = ["/today", "/timeline", "/report", "/goals"] as const;

function Gear() {
  return (
    <svg width="19" height="19" viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="12" r="3.2" stroke="currentColor" strokeWidth="1.6" />
      <path
        d="M12 2.6v2.3M12 19.1v2.3M2.6 12h2.3M19.1 12h2.3M5.3 5.3l1.7 1.7M17 17l1.7 1.7M18.7 5.3L17 7M7 17l-1.7 1.7"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function TabBar() {
  const pathname = usePathname();
  const { t } = useT();

  const labels: Record<string, string> = {
    "/today": t.nav.today,
    "/timeline": t.nav.timeline,
    "/report": t.nav.report,
    "/goals": t.nav.goals,
  };

  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-10 border-t border-line bg-ink"
      style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
    >
      <div className="mx-auto flex h-[62px] max-w-[560px]">
        {TABS.map((href) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={`flex flex-1 items-center justify-center font-mono text-[11px] uppercase tracking-[0.12em] transition-colors ${
                active ? "text-sunrise" : "text-label"
              }`}
            >
              <span className={active ? "border-b-2 border-sunrise pb-[3px]" : "pb-[3px]"}>
                {labels[href]}
              </span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}

/** For screens that take over the display entirely, like recording. */
export function BareShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!isSignedIn()) router.replace("/login");
    else setReady(true);
  }, [router]);

  if (!ready) return <div className="min-h-dvh bg-ink" aria-hidden />;
  return <div className="min-h-dvh bg-ink">{children}</div>;
}

export function Shell({
  children,
  title,
  showSettings = false,
  flush = false,
}: {
  children: ReactNode;
  title?: string;
  showSettings?: boolean;
  /** Today manages its own vertical rhythm; other screens get the standard top space. */
  flush?: boolean;
}) {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!isSignedIn()) router.replace("/login");
    else setReady(true);
  }, [router]);

  useEffect(() => {
    // The install event fires early and only once, so catch it here rather than on
    // whichever screen happens to offer the button.
    const stop = watchForInstallPrompt();
    void activeRegistration();
    return stop;
  }, []);

  if (!ready) return <div className="min-h-dvh bg-ink" aria-hidden />;

  return (
    <div className="min-h-dvh bg-ink">
      <div
        className={`mx-auto flex min-h-dvh max-w-[560px] flex-col px-[26px] pb-[62px] ${
          flush ? "" : "pt-6"
        }`}
      >
        {(title || showSettings) && (
          <header className="flex items-center justify-between">
            {title ? (
              <h1 className="font-display text-[24px] font-medium">{title}</h1>
            ) : (
              <span />
            )}
            {showSettings && (
              <Link
                href="/settings"
                aria-label="Settings"
                className="press -m-2 p-2 text-label transition-colors hover:text-bone"
              >
                <Gear />
              </Link>
            )}
          </header>
        )}
        {children}
      </div>
      <TabBar />
    </div>
  );
}
