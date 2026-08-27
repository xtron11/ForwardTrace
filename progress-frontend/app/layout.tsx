import type { Metadata, Viewport } from "next";
import { Bricolage_Grotesque, JetBrains_Mono, Source_Serif_4 } from "next/font/google";

import "./globals.css";

const bricolage = Bricolage_Grotesque({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  variable: "--font-bricolage",
});

const serif = Source_Serif_4({
  subsets: ["latin"],
  weight: ["400", "600"],
  style: ["normal", "italic"],
  variable: "--font-serif",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono-face",
});

export const metadata: Metadata = {
  title: "ForwardTrace",
  description: "Speak for thirty seconds a day. Get proof you moved.",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    title: "ForwardTrace",
    statusBarStyle: "default",
  },
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
    <html lang="en" className={`${bricolage.variable} ${serif.variable} ${mono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
