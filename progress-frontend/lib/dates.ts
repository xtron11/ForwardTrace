/** Calendar dates as "YYYY-MM-DD" strings, the form the API speaks. Arithmetic goes
 *  through UTC so that daylight-saving shifts never move a day. */

import type { Locale } from "./i18n";

function parts(ymd: string): [number, number, number] {
  const [y, m, d] = ymd.split("-").map(Number);
  return [y, m, d];
}

export function toYmd(date: Date): string {
  return date.toISOString().slice(0, 10);
}

export function addDays(ymd: string, days: number): string {
  const [y, m, d] = parts(ymd);
  return toYmd(new Date(Date.UTC(y, m - 1, d + days)));
}

/** Monday of the week the date falls in (weeks run Monday to Sunday, like the limit). */
export function weekStart(ymd: string): string {
  const [y, m, d] = parts(ymd);
  const weekday = new Date(Date.UTC(y, m - 1, d)).getUTCDay(); // 0 = Sunday
  return addDays(ymd, -((weekday + 6) % 7));
}

/** Today's date in a given IANA time zone, falling back to the device's own. */
export function todayIn(timeZone?: string | null): string {
  try {
    return new Intl.DateTimeFormat("en-CA", { timeZone: timeZone || undefined }).format(new Date());
  } catch {
    return new Intl.DateTimeFormat("en-CA").format(new Date());
  }
}

/** A date written for a person: "26 октября" / "October 26". */
export function formatDay(
  ymd: string,
  locale: Locale,
  options: Intl.DateTimeFormatOptions = { day: "numeric", month: "long" },
): string {
  const [y, m, d] = parts(ymd);
  return new Intl.DateTimeFormat(locale, { ...options, timeZone: "UTC" }).format(
    new Date(Date.UTC(y, m - 1, d)),
  );
}

/** "пн" / "Mon". */
export function weekdayShort(ymd: string, locale: Locale): string {
  return formatDay(ymd, locale, { weekday: "short" });
}

/** "1 / 2 / 5 минут"-style choice for Russian; English takes one/other. */
export function plural(locale: Locale, n: number, forms: { one: string; few: string; many: string }): string {
  if (locale === "en") return n === 1 ? forms.one : forms.many;
  const tens = n % 100;
  const ones = n % 10;
  if (tens >= 11 && tens <= 14) return forms.many;
  if (ones === 1) return forms.one;
  if (ones >= 2 && ones <= 4) return forms.few;
  return forms.many;
}
