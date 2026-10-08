import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function initials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("");
}

export const isEmbedded = () => {
  try {
    return window.self !== window.top;
  } catch {
    return true;
  }
};

export function safeStorage() {
  return {
    get(key: string): string | null {
      try {
        return window.localStorage.getItem(key);
      } catch {
        return null;
      }
    },
    set(key: string, value: string) {
      try {
        window.localStorage.setItem(key, value);
      } catch {
        /* private mode or blocked storage: keep working without persistence */
      }
    },
    remove(key: string) {
      try {
        window.localStorage.removeItem(key);
      } catch {
        /* ignore */
      }
    },
  };
}
