// Live sync between open DealMeet windows.
// Every successful write (POST) is announced on a BroadcastChannel; every
// other open window refetches what it shows, so a creator tab and a brand tab
// stay in step without a server push.
import type { QueryClient } from "@tanstack/react-query";

export interface SyncEvent {
  type: "changed";
  path: string;
  at: number;
  from: string;
}

const CHANNEL = "jd-sync";
const FRAME_ID = Math.random().toString(36).slice(2, 10);
const channel: BroadcastChannel | null = typeof BroadcastChannel === "undefined" ? null : new BroadcastChannel(CHANNEL);
const listeners = new Set<(e: SyncEvent) => void>();

channel?.addEventListener("message", (msg: MessageEvent<SyncEvent>) => {
  if (msg.data?.type === "changed" && msg.data.from !== FRAME_ID) listeners.forEach((l) => l(msg.data));
});

export function announceChange(path: string) {
  channel?.postMessage({ type: "changed", path, at: Date.now(), from: FRAME_ID } satisfies SyncEvent);
}

export function onSync(fn: (e: SyncEvent) => void) {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

export function startSync(client: QueryClient) {
  return onSync(() => {
    void client.invalidateQueries();
  });
}

export const syncAvailable = channel !== null;
