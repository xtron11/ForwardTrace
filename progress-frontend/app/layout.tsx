import type { Metadata, Viewport } from "next";
import { Bricolage_Grotesque, JetBrains_Mono, Onest, Source_Serif_4 } from "next/font/google";

import { SITE_URL } from "@/lib/site";
import { THEME_BOOTSTRAP } from "@/lib/theme";

import "./globals.css";

const bricolage = Bricolage_Grotesque({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
});

/** Cyrillic for headings: Bricolage has none, and Onest is the closest grotesque that does. */
const displayCyrillic = Onest({
  subsets: ["cyrillic"],
  weight: ["500", "600", "700"],
});

// Only the first name in Bricolage's stack: next/font follows it with a metric-adjusted
// Arial that covers every glyph, so Cyrillic would stop there and never reach Onest.
// adjustFontFallback: false would drop it, but Turbopack ignores that option.
const displayStack = `${bricolage.style.fontFamily.split(",")[0]}, ${displayCyrillic.style.fontFamily}`;

const serif = Source_Serif_4({
  subsets: ["latin", "cyrillic"],
  weight: ["400", "600"],
  style: ["normal", "italic"],
  variable: "--font-serif",
});

const mono = JetBrains_Mono({
  subsets: ["latin", "cyrillic"],
  weight: ["400", "500"],
  variable: "--font-mono-face",
});

const TITLE = "ForwardTrace — proof that you are moving";
// Under 160 characters, and it leads with the problem rather than the product: the
// people who would search for this are searching for the feeling, not for an app.
const DESCRIPTION =
  "You have been at it for weeks and cannot tell if anything changed. Speak for thirty seconds a day and read back what did — quoted from your own words.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: TITLE,
    // Inner pages get "Report · ForwardTrace" without repeating the tagline.
    template: "%s · ForwardTrace",
  },
  description: DESCRIPTION,
  applicationName: "ForwardTrace",
  manifest: "/manifest.json",
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    url: SITE_URL,
    siteName: "ForwardTrace",
    title: TITLE,
    description: DESCRIPTION,
    images: [{ url: "/og.png", width: 1200, height: 630, alt: "ForwardTrace" }],
  },
  twitter: {
    card: "summary_large_image",
    title: TITLE,
    description: DESCRIPTION,
    images: ["/og.png"],
  },
  icons: {
    icon: "/icons/icon-192.png",
    apple: "/icons/apple-touch-icon.png",
  },
  appleWebApp: {
    capable: true,
    title: "ForwardTrace",
    statusBarStyle: "default",
  },
  // The app screens are disallowed in robots.txt as well; this covers anything that
  // reaches them through a link rather than a crawl.
  robots: { index: true, follow: true },
};

export const viewport: Viewport = {
  themeColor: "#0E1116",
  width: "device-width",
  initialScale: 1,
  // Let people zoom. Locking it is an accessibility failure, not a polish detail.
  maximumScale: 5,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${serif.variable} ${mono.variable}`}
      style={{ "--font-display-face": displayStack } as React.CSSProperties}
    >
      <head>
        {/* Applied before first paint: reading the stored choice in an effect
            would flash the wrong theme for a frame. */}
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOTSTRAP }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
