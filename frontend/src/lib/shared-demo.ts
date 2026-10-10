// On a shared URL the API resets the demo data on a timer (DEMO_RESET_MINUTES), and every
// visitor sees the same data. Screens use this to say so next to the Reset buttons.
import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import type { Health } from "./types";

export function useHealth() {
  return useQuery({ queryKey: ["health"], queryFn: () => api<Health>("/health"), staleTime: 60_000 });
}

export function useSharedDemo(): boolean {
  return !!useHealth().data?.shared_demo;
}
