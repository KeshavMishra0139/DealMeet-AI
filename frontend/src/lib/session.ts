// Who is using the app right now. Creator and brand personas are stored
// separately so a creator phone and a brand console can run side by side.
// `?as=<id>` pins a persona for one frame (used by the demo screens) and
// `?embed=1` marks a frame rendered inside a phone or browser mock.
import { useSyncExternalStore } from "react";
import { safeStorage } from "./utils";

const store = safeStorage();
const KEYS = { creator: "jd.creator", brand: "jd.brand" } as const;
const DEFAULTS = { creator: "cr_a", brand: "br_senpai" } as const;

type Role = keyof typeof KEYS;
const pinned: Partial<Record<Role, string>> = {};
let embedded = false;
const listeners = new Set<() => void>();

(function readUrlOnce() {
  if (typeof window === "undefined") return;
  const params = new URLSearchParams(window.location.search);
  const as = params.get("as");
  if (as?.startsWith("cr_")) pinned.creator = as;
  if (as?.startsWith("br_")) pinned.brand = as;
  embedded = params.get("embed") === "1";
})();

function emit() {
  listeners.forEach((l) => l());
}

export function getPersona(role: Role): string {
  return pinned[role] ?? store.get(KEYS[role]) ?? DEFAULTS[role];
}

export function setPersona(role: Role, id: string) {
  delete pinned[role];
  store.set(KEYS[role], id);
  emit();
}

export function isEmbedFrame() {
  return embedded;
}

function subscribe(fn: () => void) {
  listeners.add(fn);
  const onStorage = (e: StorageEvent) => {
    if (e.key === KEYS.creator || e.key === KEYS.brand) fn();
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(fn);
    window.removeEventListener("storage", onStorage);
  };
}

export function useCreatorId() {
  return useSyncExternalStore(subscribe, () => getPersona("creator"));
}

export function useBrandId() {
  return useSyncExternalStore(subscribe, () => getPersona("brand"));
}
