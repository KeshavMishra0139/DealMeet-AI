import { useEffect } from "react";

export type Theme = "creator" | "brand";

/** Applies a theme to <html> so the page background and scrollbars match. */
export function useTheme(theme: Theme) {
  useEffect(() => {
    const html = document.documentElement;
    html.classList.remove("theme-creator", "theme-brand");
    html.classList.add(`theme-${theme}`);
    const meta = document.querySelector('meta[name="theme-color"]');
    meta?.setAttribute("content", theme === "creator" ? "#0B0A1A" : "#F8F7FC");
  }, [theme]);
}
