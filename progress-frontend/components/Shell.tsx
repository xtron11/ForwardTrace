"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { isSignedIn } from "@/lib/api";
import { activeRegistration } from "@/lib/push";
import { watchForInstallPrompt } from "@/lib/pwa";
import { useTheme } from "@/lib/theme";
import { useT } from "@/lib/useT";

/**
 * Four destinations, no more. Settings sits behind the gear on Today and signing out
 * sits inside settings: both are rare, and six tabs do not fit a phone.
 */
const TABS = ["/today", "/timeline", "/report", "/goals"] as const;

/** A cog with actual teeth. The earlier version was a ring with rays, which reads as a
 *  brightness control - exactly the thing sitting next to it. */
function Gear() {
  return (
    <svg width="19" height="19" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M19.4 13a7.6 7.6 0 0 0 0-2l2-1.6a.5.5 0 0 0 .1-.6l-1.9-3.2a.5.5 0 0 0-.6-.2l-2.4 1a7.4 7.4 0 0 0-1.7-1l-.4-2.5a.5.5 0 0 0-.5-.4h-3.8a.5.5 0 0 0-.5.4l-.4 2.5a7.4 7.4 0 0 0-1.7 1l-2.4-1a.5.5 0 0 0-.6.2L2.5 8.8a.5.5 0 0 0 .1.6L4.6 11a7.6 7.6 0 0 0 0 2l-2 1.6a.5.5 0 0 0-.1.6l1.9 3.2a.5.5 0 0 0 .6.2l2.4-1a7.4 7.4 0 0 0 1.7 1l.4 2.5a.5.5 0 0 0 .5.4h3.8a.5.5 0 0 0 .5-.4l.4-2.5a7.4 7.4 0 0 0 1.7-1l2.4 1a.5.5 0 0 0 .6-.2l1.9-3.2a.5.5 0 0 0-.1-.6Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <circle cx="12" cy="12" r="2.8" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

function Sun() {
  return (
    <svg width="19" height="19" viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="12" r="4" stroke="currentColor" strokeWidth="1.6" />
      <path
        d="M12 2.5v2.2M12 19.3v2.2M2.5 12h2.2M19.3 12h2.2M5.6 5.6l1.6 1.6M16.8 16.8l1.6 1.6M18.4 5.6l-1.6 1.6M7.2 16.8l-1.6 1.6"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}

function Moon() {
  return (
    <svg width="19" height="19" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M20.5 14.3A8.5 8.5 0 1 1 9.7 3.5a6.8 6.8 0 0 0 10.8 10.8Z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ThemeToggle() {
  const { theme, toggle } = useTheme();
  return (
    <button
      onClick={toggle}
      aria-label={theme === "dark" ? "Light theme" : "Dark theme"}
      className="press -m-2 p-2 text-label transition-colors hover:text-bone"
    >
      {theme === "dark" ? <Sun /> : <Moon />}
    </button>
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
              <div className="flex items-center gap-4">
                <ThemeToggle />
                <Link
                  href="/settings"
                  aria-label="Settings"
                  className="press -m-2 p-2 text-label transition-colors hover:text-bone"
                >
                  <Gear />
                </Link>
              </div>
            )}
          </header>
        )}
        {children}
      </div>
      <TabBar />
    </div>
  );
}
