import type { Metadata } from "next";

import { NotFound } from "@/components/NotFound";

/** One root layout, so this covers unmatched URLs as well as notFound() calls. */
export const metadata: Metadata = {
  title: "404",
  robots: { index: false, follow: false },
};

export default function NotFoundPage() {
  return <NotFound />;
}
