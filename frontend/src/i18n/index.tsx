import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { safeStorage } from "@/lib/utils";
import { en, type Dict } from "./en";
import { hi } from "./hi";

export type Lang = "en" | "hi";
const dicts: Record<Lang, Dict> = { en, hi };
const store = safeStorage();

interface I18n {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (key: keyof Dict) => string;
}

const Ctx = createContext<I18n>({ lang: "en", setLang: () => {}, t: (k) => en[k] });

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => (store.get("jd.lang") === "hi" ? "hi" : "en"));
  const setLang = useCallback((l: Lang) => {
    store.set("jd.lang", l);
    setLangState(l);
  }, []);
  const value = useMemo<I18n>(
    () => ({ lang, setLang, t: (key) => dicts[lang][key] ?? en[key] }),
    [lang, setLang],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export const useI18n = () => useContext(Ctx);
