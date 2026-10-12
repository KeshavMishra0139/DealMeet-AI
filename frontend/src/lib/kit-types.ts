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
  /** "your_rate" when the creator saved their own rates, else DealMeet's estimated ranges. */
  rates_kind?: "your_rate" | "estimate" | null;
  /** Null when the creator hides rates on the public page. */
  from_rate: number | null;
  trust: { score: number; level: "high" | "medium" | "low"; reasons: string[] } | null;
  safety_note: string | null;
  public?: { stats: boolean; demographics: boolean; rates: boolean; collabs?: boolean };
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

export interface PageBadge {
  key: "connected" | "on_time" | "completed" | "rating" | "collective";
  label: string;
  detail: string;
  sample: boolean;
}

/** The full public creator page: the kit plus what only the page shows. */
export interface PublicPage extends Kit {
  niche_tags: string[];
  positioning: string | null;
  badges: PageBadge[];
  collaborations: { brand: string; slug: string | null; month: string | null; deliverables: string; sample: boolean }[] | null;
  top_posts: { platform: string; url: string | null; text: string; views: number | null; views_label: string; published_at: string | null; source: DataSource }[] | null;
  fan_badges: { brand: string; slug: string | null; label: string }[];
  case_studies:
    | { brand: string | null; predicted_views: number; predicted_label: string; predicted_source: string | null; actual_views: number | null; actual_label: string | null; actual_source: string | null; paid_in_days?: number; sample: boolean }[]
    | null;
  estimate: { range: { low: number; high: number }; deliverables: string; label: string; data_label: string; data_source: string } | null;
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
