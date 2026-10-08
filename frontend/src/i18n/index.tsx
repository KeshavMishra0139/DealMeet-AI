import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { safeStorage } from "@/lib/utils";
import { en, type Dict } from "./en";
import { hi, hiPhrases } from "./hi";

export type Lang = "en" | "hi";
const dicts: Record<Lang, Dict> = { en, hi };
const store = safeStorage();

// `?lang=hi` or `?lang=en` in a link picks the language (and is remembered).
(function readUrlOnce() {
  if (typeof window === "undefined") return;
  const v = new URLSearchParams(window.location.search).get("lang");
  if (v === "hi" || v === "en") store.set("jd.lang", v);
})();

type Vars = Record<string, string | number>;

interface I18n {
  /** Language in effect here. Hindi applies inside <LangScope> (the Creator Studio); elsewhere it's English. */
  lang: Lang;
  /** The creator's chosen language, wherever we are. */
  chosen: Lang;
  setLang: (l: Lang) => void;
  t: (key: keyof Dict, vars?: Vars) => string;
  /** Picks the Hindi variant of server copy when present: pick(move.title, move.hi?.title). */
  pick: (english: string, hindi?: string | null) => string;
}

function fill(text: string, vars?: Vars) {
  return vars ? text.replace(/\{(\w+)\}/g, (_, k: string) => String(vars[k] ?? `{${k}}`)) : text;
}

function make(lang: Lang, chosen: Lang, setLang: (l: Lang) => void): I18n {
  return {
    lang,
    chosen,
    setLang,
    t: (key, vars) => fill(dicts[lang][key] ?? en[key], vars),
    pick: (english, hindi) => (lang === "hi" && hindi ? hindi : english),
  };
}

const Ctx = createContext<I18n>(make("en", "en", () => {}));

export function I18nProvider({ children }: { children: ReactNode }) {
  const [chosen, setChosen] = useState<Lang>(() => (store.get("jd.lang") === "hi" ? "hi" : "en"));
  const setLang = useCallback((l: Lang) => {
    store.set("jd.lang", l);
    setChosen(l);
  }, []);
  const value = useMemo(() => make("en", chosen, setLang), [chosen, setLang]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

/** Applies the creator's chosen language to everything inside (the Creator Studio screens). */
export function LangScope({ children }: { children: ReactNode }) {
  const { chosen, setLang } = useContext(Ctx);
  const value = useMemo(() => make(chosen, chosen, setLang), [chosen, setLang]);
  return (
    <Ctx.Provider value={value}>
      <div lang={chosen} className="contents">
        {children}
      </div>
    </Ctx.Provider>
  );
}

export const useI18n = () => useContext(Ctx);

/** Translates fixed server phrases (CTA labels, headlines) when a Hindi version exists. */
export function useTr() {
  const { lang } = useI18n();
  return (english: string) => (lang === "hi" ? hiPhrases[english] ?? english : english);
}
