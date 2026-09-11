/** The canonical address, used by metadata, robots.txt and the sitemap.
 *
 *  Set NEXT_PUBLIC_SITE_URL in the deployment. Without it these files would advertise
 *  localhost, and a sitemap pointing at localhost is worse than none.
 */
export const SITE_URL = (
  process.env.NEXT_PUBLIC_SITE_URL ?? "https://forward-trace.com"
).replace(/\/$/, "");
