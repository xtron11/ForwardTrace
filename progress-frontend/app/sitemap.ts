import type { MetadataRoute } from "next";

import { SITE_URL } from "@/lib/site";

/**
 * Only pages worth landing on from a search. The app itself is behind a sign-in and
 * has nothing to offer a crawler.
 */
export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();
  return [
    { url: SITE_URL, lastModified: now, changeFrequency: "weekly", priority: 1 },
    { url: `${SITE_URL}/register`, lastModified: now, changeFrequency: "monthly", priority: 0.5 },
    { url: `${SITE_URL}/login`, lastModified: now, changeFrequency: "monthly", priority: 0.3 },
  ];
}
