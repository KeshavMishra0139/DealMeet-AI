// The languages the AI writes in (backend: ai/regional.py WRITE_IN). English and Hindi also
// have built-in templates; the others need the AI, and fall back to English without it.
export const WRITE_LANGS = [
  { value: "en", label: "English" },
  { value: "hi", label: "हिंदी" },
  { value: "hinglish", label: "Hinglish" },
  { value: "ta", label: "தமிழ்" },
  { value: "te", label: "తెలుగు" },
  { value: "kn", label: "ಕನ್ನಡ" },
  { value: "ml", label: "മലയാളം" },
  { value: "bn", label: "বাংলা" },
  { value: "mr", label: "मराठी" },
  { value: "gu", label: "ગુજરાતી" },
] as const;

export type WriteLang = (typeof WRITE_LANGS)[number]["value"];

export function isWriteLang(v: string | null | undefined): v is WriteLang {
  return WRITE_LANGS.some((l) => l.value === v);
}

export function langLabel(v: string | null | undefined): string {
  return WRITE_LANGS.find((l) => l.value === v)?.label ?? "English";
}

/** A valid HTML lang attribute (Hinglish is Hindi in Latin script). */
export function htmlLang(v: string | null | undefined): string {
  return v === "hinglish" ? "hi-Latn" : (v ?? "en");
}
