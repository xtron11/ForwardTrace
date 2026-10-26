"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { Logo } from "@/components/Logo";
import { Button } from "@/components/ui";
import { ApiError, api, clearTokens, isSignedIn } from "@/lib/api";
import { toLocale } from "@/lib/i18n";
import { activeRegistration } from "@/lib/push";
import { watchForInstallPrompt } from "@/lib/pwa";
import type { User } from "@/lib/types";
import { setLocale, useT } from "@/lib/useT";

type UserState = {
  user: User;
  /** Replace the cached user after a PATCH /api/auth/me. Also re-applies the locale. */
  setUser: (user: User) => void;
  signOut: () => void;
};

const UserContext = createContext<UserState | null>(null);

/** The signed-in person. Only usable inside AppShell, which renders children after the
 *  user has loaded. */
export function useUser(): UserState {
  const ctx = useContext(UserContext);
  if (!ctx) throw new Error("useUser must be used inside AppShell");
  return ctx;
}

/** Bottom tabs. `match` also keeps a tab lit on its sub-pages (/history/2026-10-01). */
const TABS = [
  { href: "/today", key: "today" },
  { href: "/history", key: "history" },
  { href: "/progress", key: "progress" },
] as const;

function Gear() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden>
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

function TabBar() {
  const pathname = usePathname();
  const { t } = useT();

  return (
    <nav
      aria-label={t.nav.primary}
      className="fixed inset-x-0 bottom-0 z-10 border-t border-line bg-ink"
      style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
    >
      <div className="mx-auto flex h-(--bar-height) max-w-(--column-max)">
        {TABS.map(({ href, key }) => {
          const active = pathname === href || pathname.startsWith(`${href}/`);
          return (
            <Link
              key={href}
              href={href}
              aria-current={active ? "page" : undefined}
              className={`flex flex-1 items-center justify-center font-mono text-[length:var(--text-label)] uppercase tracking-[0.12em] transition-colors ${
                active ? "text-sunrise" : "text-label hover:text-bone"
              }`}
            >
              <span className={active ? "border-b-2 border-sunrise pb-0.5" : "pb-0.5"}>
                {t.nav[key]}
              </span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}

/**
 * The frame of every signed-in screen: a top bar with the gear at the right, the
 * screen, and the bottom tabs. It also does the sign-in guard and loads the user, whose
 * `locale` sets the interface language and <html lang>.
 *
 * It sits in app/(app)/layout.tsx, so it stays mounted while moving between tabs.
 */
export function AppShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { t } = useT();
  const [user, setUserState] = useState<User | null>(null);
  const [failed, setFailed] = useState(false);

  const load = useCallback(async () => {
    setFailed(false);
    try {
      const me = await api.me();
      setLocale(toLocale(me.locale));
      setUserState(me);
    } catch (err) {
      // 401 means the tokens are dead (api.ts has cleared them); go and sign in.
      if (err instanceof ApiError && err.status === 401) router.replace("/login");
      else setFailed(true);
    }
  }, [router]);

  useEffect(() => {
    if (!isSignedIn()) {
      router.replace("/login");
      return;
    }
    void load();
  }, [router, load]);

  useEffect(() => {
    // The install event fires early and only once, so catch it here rather than on
    // whichever screen happens to offer the button.
    const stop = watchForInstallPrompt();
    void activeRegistration();
    return stop;
  }, []);

  const value = useMemo<UserState | null>(
    () =>
      user && {
        user,
        setUser: (next) => {
          setLocale(toLocale(next.locale));
          setUserState(next);
        },
        signOut: () => {
          clearTokens();
          router.replace("/login");
        },
      },
    [user, router],
  );

  if (failed) {
    return (
      <div className="flex min-h-dvh flex-col items-center justify-center gap-4 bg-ink px-(--page-pad) text-center">
        <p className="text-dim">{t.errors.offline}</p>
        <Button variant="quiet" onClick={() => void load()}>
          {t.shell.retry}
        </Button>
      </div>
    );
  }

  if (!value) {
    return (
      <div className="min-h-dvh bg-ink" aria-busy="true" aria-label={t.shell.loading} />
    );
  }

  return (
    <UserContext.Provider value={value}>
      <div className="min-h-dvh bg-ink">
        <div className="mx-auto flex min-h-dvh max-w-(--column-max) flex-col pb-(--bar-height)">
          <header className="flex h-(--header-height) items-center justify-between px-(--page-pad)">
            <Link href="/today" aria-label={t.brand} className="text-bone">
              <Logo size={28} />
            </Link>
            <Link
              href="/profile"
              aria-label={t.nav.settings}
              className="press -m-2 p-2 text-label transition-colors hover:text-bone"
            >
              <Gear />
            </Link>
          </header>
          <main className="flex flex-1 flex-col px-(--page-pad) pb-6">{children}</main>
        </div>
        <TabBar />
      </div>
    </UserContext.Provider>
  );
}
