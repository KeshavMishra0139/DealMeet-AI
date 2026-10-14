// Phone frames for the guided demo pages, and the messages between those pages and the
// copies of the app running inside their frames.
export const PHONE = { width: 390, height: 844 } as const;

/** True when a key press should not be treated as a shortcut (typing, or a modifier is held). */
export function isTypingTarget(e: KeyboardEvent) {
  if (e.metaKey || e.ctrlKey || e.altKey) return true;
  const el = e.target as HTMLElement | null;
  if (!el) return false;
  return el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName) || el.getAttribute("role") === "textbox";
}

// Messages between a demo page and the app running inside its frames (same origin only).
export type FrameMessage =
  | { type: "jd:navigate"; to: string }
  | { type: "jd:route"; path: string };

export function postToParent(msg: FrameMessage) {
  if (window.parent !== window) window.parent.postMessage(msg, window.location.origin);
}

export function postToFrame(frame: HTMLIFrameElement | null, msg: FrameMessage) {
  frame?.contentWindow?.postMessage(msg, window.location.origin);
}

/** Adds embed=1 (and optionally a pinned persona) to an app path for use in a frame. */
export function framePath(path: string, as?: string) {
  const url = new URL(path, window.location.origin);
  url.searchParams.set("embed", "1");
  if (as) url.searchParams.set("as", as);
  return `${url.pathname}${url.search}${url.hash}`;
}

/** The inverse of framePath: what the address bar should show for a frame's location. */
export function publicPath(path: string) {
  const url = new URL(path, window.location.origin);
  url.searchParams.delete("embed");
  const q = url.searchParams.toString();
  return `${url.pathname}${q ? `?${q}` : ""}${url.hash}`;
}
