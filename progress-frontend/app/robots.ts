import type { MetadataRoute } from "next";

import { SITE_URL } from "@/lib/site";

/**
 * Almost everything here sits behind a sign-in, so almost everything is disallowed.
 *
 * Letting crawlers at /today or /report would put empty auth-gated shells in search
 * results - pages that show a visitor nothing and teach the search engine that the
 * site is thin. Only the landing page and the two auth screens describe anything.
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: [
        "/today",
        "/record",
        "/report",
        "/monthly",
        "/timeline",
        "/goals",
        "/settings",
        "/setup",
        "/verify",
        "/api/",
      ],
    },
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  };
}
