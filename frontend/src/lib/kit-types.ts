import type { DataSource } from "@/components/shared/SourceBadge";

export type KitLang = "en" | "hi";
export type KitSection = "stats" | "formats" | "audience" | "rates" | "trust";

export interface Kit {
  creator_id: string;
  /** The kit's own language, which can differ from the app's. */
  lang: KitLang;
  name: string;
  handle: string;
  avatar_hue: number;
  is_reference: boolean;
  reference_note: string | null;
  niche: string;
  languages: string[];
  location: string | null;
  copy: { headline: string; bio: string };
  copy_source: "ai" | "cache" | "template" | "creator";
  stats: { label: string; value: string; simulated: boolean; source?: DataSource }[] | null;
  formats: { topic: string; views: string; simulated: boolean; source?: DataSource }[] | null;
  audience: { line: string; simulated: boolean; source?: DataSource } | null;
  rates: { label: string; value: string; kind?: "your_rate" | "estimate" }[] | null;
  /** "your_rate" when the creator saved their own rates, else JodiDar's estimated ranges. */
  rates_kind?: "your_rate" | "estimate" | null;
  /** Null when the creator hides rates on the public page. */
  from_rate: number | null;
  trust: { score: number; level: "high" | "medium" | "low"; reasons: string[] } | null;
  safety_note: string | null;
  public?: { stats: boolean; demographics: boolean; rates: boolean };
  sections?: Record<KitSection, boolean>;
  /** Set when this is a saved version; null for the live view. */
  version?: { number: number; saved_on: string } | null;
  /** The owner's view only: the version the public page shows, or null for the live view. */
  public_version?: string | null;
  link: string;
  path: string;
  generated_on: string;
  has_simulated: boolean;
}

export interface KitVersion {
  id: string;
  number: number;
  lang: KitLang;
  headline: string;
  sections: Record<KitSection, boolean>;
  created_at: string;
  pdf_bytes: number;
  pdf_sha256: string;
  published: boolean;
}
