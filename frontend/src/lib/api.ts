import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";
import { activeRole, forgetToken, tokenFor, type Role } from "./session";
import { announceChange } from "./sync";

const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? "/api";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

type ApiInit = RequestInit & {
  json?: unknown;
  /** Which side's demo token to send. Defaults to the side this page belongs to; null sends none. */
  role?: Role | null;
};

export async function api<T>(path: string, init?: ApiInit): Promise<T> {
  const { json, headers, role, ...rest } = init ?? {};
  const token = role === null ? undefined : tokenFor(role ?? activeRole());
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      credentials: "same-origin",
      ...rest,
      headers: {
        // Every write must carry this header: a cross-site form can't, so a cookie alone never changes anything.
        "X-Requested-With": "jodidar",
        ...(json !== undefined ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...headers,
      },
      body: json !== undefined ? JSON.stringify(json) : rest.body,
    });
  } catch {
    throw new ApiError(0, "Can't reach JodiDar right now. Check your connection and try again.");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : detail;
    } catch {
      /* not JSON */
    }
    if (res.status === 401 && token) forgetToken(token);
    throw new ApiError(res.status, detail);
  }
  if (rest.method && rest.method !== "GET" && !path.startsWith("/auth/")) announceChange(path);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const post = <T>(path: string, json?: unknown) => api<T>(path, { method: "POST", json: json ?? {} });

/** A 401 anywhere means the session ended: re-check it, so the shell signs in again or sends you to sign-in. */
function onAuthError(err: unknown, key?: readonly unknown[]) {
  if (err instanceof ApiError && err.status === 401 && key?.[0] !== "session") {
    void queryClient.invalidateQueries({ queryKey: ["session"] });
  }
}

export const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: (err, query) => onAuthError(err, query.queryKey) }),
  mutationCache: new MutationCache({ onError: (err) => onAuthError(err) }),
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      retry: (n, err) => !(err instanceof ApiError && [401, 403, 404].includes(err.status)) && n < 2,
      refetchOnWindowFocus: false,
    },
  },
});
