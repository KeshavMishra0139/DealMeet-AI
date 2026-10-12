import { useEffect } from "react";

export type Theme = "site" | "creator" | "brand";

const THEME_COLOR: Record<Theme, string> = { site: "#F9FAFB", creator: "#0B0A1A", brand: "#F9FAFB" };

/** Applies a theme to <html> so the page background and scrollbars match. */
export function useTheme(theme: Theme) {
  useEffect(() => {
    const html = document.documentElement;
    html.classList.remove("theme-site", "theme-creator", "theme-brand");
    html.classList.add(`theme-${theme}`);
    const meta = document.querySelector('meta[name="theme-color"]');
    meta?.setAttribute("content", THEME_COLOR[theme]);
  }, [theme]);
}
