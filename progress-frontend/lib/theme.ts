"use client";

import { useEffect, useState } from "react";

export type Theme = "dark" | "light";

const KEY = "forwardtrace.theme";

/** Runs before paint, injected in the document head. Reading the stored choice in a
 *  React effect would show one theme for a frame and then swap, which is worse than
 *  either theme on its own. */
export const THEME_BOOTSTRAP = `(function(){try{
var t=localStorage.getItem(${JSON.stringify(KEY)});
if(t!=="light"&&t!=="dark"){t=window.matchMedia("(prefers-color-scheme: light)").matches?"light":"dark";}
document.documentElement.setAttribute("data-theme",t);
}catch(e){document.documentElement.setAttribute("data-theme","dark");}})();`;

function current(): Theme {
  if (typeof document === "undefined") return "dark";
  return document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
}

function apply(theme: Theme) {
  document.documentElement.setAttribute("data-theme", theme);
  // Keep the browser chrome in step with the page.
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute("content", theme === "light" ? "#F4F1EA" : "#0E1116");
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>("dark");

  useEffect(() => {
    setTheme(current());
  }, []);

  function toggle() {
    const next: Theme = current() === "dark" ? "light" : "dark";
    apply(next);
    try {
      localStorage.setItem(KEY, next);
    } catch {
      /* private mode: the choice just will not persist */
    }
    setTheme(next);
  }

  return { theme, toggle };
}
