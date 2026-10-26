import { readFileSync } from "node:fs";
import { join } from "node:path";

import type { Viewport } from "next";

/** The colour of the browser chrome for each system theme: `--ink` of each skin, read
 *  from tokens.css so that file stays the only one holding literal colours. Server only;
 *  without the file (or the variable) there is no theme-color, not a wrong one. */
export function themeColors(): Viewport["themeColor"] {
  try {
    const css = readFileSync(join(process.cwd(), "app", "tokens.css"), "utf8");
    const ink = (skin: "dark" | "light") =>
      new RegExp(`\\[data-theme="${skin}"\\]\\s*\\{[^}]*?--ink:\\s*([^;]+);`).exec(css)?.[1]?.trim();
    const dark = ink("dark");
    const light = ink("light");
    if (!dark || !light) return undefined;
    return [
      { media: "(prefers-color-scheme: light)", color: light },
      { media: "(prefers-color-scheme: dark)", color: dark },
    ];
  } catch {
    return undefined;
  }
}
