// Phone-frame presentation mode. Toggled with the P key or the floating switch,
// remembered in localStorage, and shared by every open tab.
import { useSyncExternalStore } from "react";
import { safeStorage } from "./utils";

const KEY = "jd.phone";
const store = safeStorage();
const listeners = new Set<() => void>();

export const PHONE = { width: 390, height: 844 } as const;

// `?phone=1` or `?phone=0` in a link sets the mode, so a demo link can open straight in phone view.
(function readUrlOnce() {
  if (typeof window === "undefined") return;
  const v = new URLSearchParams(window.location.search).get("phone");
  if (v === "1" || v === "0") store.set(KEY, v);
})();

export function isPhoneMode() {
  return store.get(KEY) === "1";
}

export function setPhoneMode(on: boolean) {
  store.set(KEY, on ? "1" : "0");
  listeners.forEach((l) => l());
}

export function togglePhoneMode() {
  setPhoneMode(!isPhoneMode());
}

function subscribe(fn: () => void) {
  listeners.add(fn);
  const onStorage = (e: StorageEvent) => {
    if (e.key === KEY) fn();
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(fn);
    window.removeEventListener("storage", onStorage);
  };
}

export function usePhoneMode() {
  return useSyncExternalStore(subscribe, isPhoneMode, () => false);
}

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
  | { type: "jd:route"; path: string }
  | { type: "jd:toggle-phone" };

export function postToParent(msg: FrameMessage) {
  if (window.parent !== window) window.parent.postMessage(msg, window.location.origin);
}

export function postToFrame(frame: HTMLIFrameElement | null, msg: FrameMessage) {
  frame?.contentWindow?.postMessage(msg, window.location.origin);
}

/** Adds embed=1 (and optionally a pinned persona) to an app path for use in a frame. */
export function framePath(path: string, as?: string) {
  const url = new URL(path, window.location.origin);
  url.searchParams.delete("phone");
  url.searchParams.set("embed", "1");
  if (as) url.searchParams.set("as", as);
  return `${url.pathname}${url.search}${url.hash}`;
}

/** The inverse of framePath: what the address bar should show for a frame's location. */
export function publicPath(path: string) {
  const url = new URL(path, window.location.origin);
  url.searchParams.delete("embed");
  url.searchParams.delete("phone");
  const q = url.searchParams.toString();
  return `${url.pathname}${q ? `?${q}` : ""}${url.hash}`;
}
