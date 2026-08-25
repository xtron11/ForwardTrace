import type { dict } from "./i18n";

type Dict = ReturnType<typeof dict>;

/** The API answers in English. Rather than leak that into a Russian page, map the
 *  messages we produce ourselves. Anything unrecognised falls through unchanged - a
 *  slightly foreign message beats swallowing a real error.
 *
 *  Stopgap: the honest fix is for the API to return a code alongside the prose, which
 *  is worth doing once the set of messages settles. */
const KNOWN: { match: RegExp; key: keyof Dict["errors"] }[] = [
  { match: /7-day period is not over/i, key: "periodNotOver" },
  { match: /Interrupted by a server restart/i, key: "interrupted" },
  { match: /No speech detected/i, key: "noSpeech" },
];

export function translateServerMessage(message: string | null | undefined, t: Dict): string {
  if (!message) return "";
  const hit = KNOWN.find((entry) => entry.match.test(message));
  return hit ? t.errors[hit.key] : message;
}
