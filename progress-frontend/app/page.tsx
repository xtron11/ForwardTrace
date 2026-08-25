"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { isSignedIn } from "@/lib/api";
import { useT } from "@/lib/useT";

export default function Landing() {
  const { t } = useT();
  const [signedIn, setSignedIn] = useState(false);
  useEffect(() => setSignedIn(isSignedIn()), []);

  return (
    <div className="min-h-dvh bg-paper">
      <div className="mx-auto max-w-[680px] px-5 py-20">
        <p className="eyebrow mb-8">{t.landing.eyebrow}</p>

        <h1 className="text-[clamp(2.4rem,7vw,3.6rem)]">
          {t.landing.headline1}
          <br />
          {t.landing.headline2}
        </h1>

        <p className="mt-7 max-w-[46ch] text-[19px] text-ink/85">
{t.landing.lede}
        </p>

        {/* The thesis, shown rather than described: a claim and its receipt. */}
        <div className="card mt-12 p-6 sm:p-8">
          <p className="eyebrow mb-3">{t.landing.dayLabel}</p>
          <p className="font-display text-[21px] leading-snug">
{t.landing.exampleClaim}
          </p>
          <p className="eyebrow mt-6 mb-2">{t.landing.exampleSaid}</p>
          <p className="font-mono text-[13px] leading-relaxed">
            <span className="mark">
{t.landing.exampleQuote}
            </span>
          </p>
        </div>

        <p className="mt-6 text-[15px] text-muted">
{t.landing.guarantee}
        </p>

        <div className="mt-12 flex flex-wrap items-center gap-4">
          <Link
            href={signedIn ? "/today" : "/register"}
            className="rounded-sm bg-signal px-6 py-3 font-display text-[15px] font-semibold text-card transition-colors hover:bg-ink"
          >
            {signedIn ? t.landing.ctaReturning : t.landing.ctaNew}
          </Link>
          {!signedIn && (
            <Link href="/login" className="text-[15px] text-signal underline underline-offset-4">
              {t.landing.haveAccount}
            </Link>
          )}
        </div>

        <div className="mt-20 border-t border-rule pt-6">
          <p className="font-mono text-[12px] leading-relaxed text-muted">
            {t.landing.footer1}
            <br />
            {t.landing.footer2}
          </p>
        </div>
      </div>
    </div>
  );
}
