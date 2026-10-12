// Who is signed in. The server decides: every request carries a session, and
// every route checks it and who owns the record.
//
// - Real accounts (email and password, or Firebase) keep their session in an
//   HttpOnly cookie the page can't read.
// - Demo mode only: the persona picker keeps a demo token per side (creator,
//   brand), so a creator phone and a brand console can run side by side, and
//   `?as=<profile id>` signs one frame in as that demo profile (kept in memory).
// - `?embed=1` marks a frame rendered inside a phone or browser mock.
import { useQuery } from "@tanstack/react-query";
import { safeStorage } from "./utils";

export type Role = "creator" | "brand";

export interface SessionUser {
  id: string;
  role: Role | "admin";
  name: string | null;
  email: string | null;
  creator_id: string | null;
  brand_id: string | null;
  demo: boolean;
  providers: string[];
}

export interface Me {
  user: SessionUser;
  profile: { id: string; name: string; handle?: string } | null;
  demo_mode: boolean;
}

const store = safeStorage();
const KEYS = { creator: "jd.token.creator", brand: "jd.token.brand" } as const;
const pinned: Partial<Record<Role, string>> = {};
const memTokens: Partial<Record<Role, string>> = {};
let embedded = false;

(function readUrlOnce() {
  if (typeof window === "undefined") return;
  const params = new URLSearchParams(window.location.search);
  const as = params.get("as");
  if (as?.startsWith("cr_") || as === "new_creator") pinned.creator = as;
  else if (as) pinned.brand = as;
  embedded = params.get("embed") === "1";
})();

export function isEmbedFrame() {
  return embedded;
}

/** The side of the app this page belongs to, from its address. */
export function activeRole(): Role | undefined {
  if (typeof window === "undefined") return undefined;
  const p = window.location.pathname;
  if (p === "/creator" || p.startsWith("/creator/")) return "creator";
  if (p === "/brand" || p.startsWith("/brand/")) return "brand";
  return undefined;
}

/** The Bearer token for a side, if this browser holds one (demo sessions only). */
export function tokenFor(role: Role | undefined): string | undefined {
  if (!role) return undefined;
  if (pinned[role]) return memTokens[role];
  return memTokens[role] ?? store.get(KEYS[role]) ?? undefined;
}

export function rememberDemoToken(role: Role, token: string) {
  if (pinned[role]) memTokens[role] = token;
  else store.set(KEYS[role], token);
}

/** Drops a token the server refused, so the next check signs in again or asks to. */
export function forgetToken(token: string) {
  for (const role of ["creator", "brand"] as Role[]) {
    if (memTokens[role] === token) delete memTokens[role];
    if (store.get(KEYS[role]) === token) store.remove(KEYS[role]);
  }
}

export function forgetRole(role: Role) {
  delete memTokens[role];
  store.remove(KEYS[role]);
}

export function forgetAllTokens() {
  for (const role of ["creator", "brand"] as Role[]) {
    delete memTokens[role];
    store.remove(KEYS[role]);
  }
}

export function pinnedPersona(role: Role): string | undefined {
  return pinned[role];
}

// Imported lazily to avoid a cycle (api.ts reads tokens from here).
async function http() {
  return import("./api");
}

async function loadSession(role: Role): Promise<Me | null> {
  const { api, ApiError } = await http();
  const pin = pinned[role];
  if (pin && !memTokens[role]) {
    const r = await api<{ token: string }>("/auth/demo", { method: "POST", json: { persona: pin, cookie: false }, role: null });
    memTokens[role] = r.token;
  }
  try {
    return await api<Me>("/auth/me", { role });
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) return null;
    throw e;
  }
}

/** The signed-in account for one side of the app, or null when nobody is signed in. */
export function useSession(role: Role, enabled = true) {
  return useQuery({
    queryKey: ["session", role, pinned[role] ?? ""],
    queryFn: () => loadSession(role),
    staleTime: Infinity,
    retry: false,
    enabled,
  });
}

/** True when this browser holds (or this frame pins) a demo session for a side. Real
 * accounts use an HttpOnly cookie the page can't see; the server reports those. */
export function hasDemoSession(role: Role): boolean {
  return !!pinned[role] || !!tokenFor(role);
}

export function useCreatorId(): string {
  return useSession("creator").data?.user.creator_id ?? "";
}

export function useBrandId(): string {
  return useSession("brand").data?.user.brand_id ?? "";
}

/** The profile id to pin when this page opens itself in a frame (phone view), demo accounts only. */
export function framePersona(me: Me | null | undefined): string | undefined {
  if (!me?.user.demo) return undefined;
  return me.user.creator_id ?? me.user.brand_id ?? undefined;
}
