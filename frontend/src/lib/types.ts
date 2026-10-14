export type Provenance = "real" | "simulated" | "seed";

export interface WhyInput {
  label: string;
  value: string;
  provenance?: Provenance;
}

export interface Why {
  title?: string;
  reasons: string[];
  inputs?: WhyInput[];
  simulated_fields?: string[];
  source?: string;
}

export type Confidence = "low" | "medium" | "high";

export interface Estimate {
  low: number;
  high: number;
  unit: "inr" | "views" | "followers" | "reach";
  period?: "month" | "reel" | "week" | "deal" | null;
  assumptions: string[];
  confidence: Confidence;
}

export interface Persona {
  id: string;
  role: "creator" | "brand" | "admin";
  title: string;
  subtitle: string;
  tag: string;
}

export interface Health {
  status: string;
  today: string;
  modes: { db: string; ai: string; payments: string; auth: string; tee?: "not_configured" | "available" | "failed" };
  /** Persona sign-in, seeded data and the Reset button exist only in demo mode. */
  demo_mode?: boolean;
  /** True on a shared URL where the demo resets itself on a timer. */
  shared_demo?: boolean;
}

export interface Reel {
  id: string;
  date: string;
  views: number;
  likes: number;
  saves: number;
  shares: number;
  comments: number;
  topic: string;
  caption: string | null;
  lang: string | null;
  copyrighted_clips: boolean;
  is_recent: boolean;
}

export interface Creator {
  /** The words for this creator's posts and audience: videos and subscribers on YouTube. */
  terms?: { platform: "youtube" | "instagram"; post: string; posts: string; audience: string };
  id: string;
  handle: string;
  name: string;
  avatar_hue: number;
  is_reference: boolean;
  reference_note: string;
  bio: string;
  niche: string;
  niche_label: string;
  languages: string[];
  language_labels: string[];
  city: string | null;
  region: string | null;
  formats?: string[];
  /** Set up from YouTube or Instagram instead of the form: what to review (e.g. "city"). */
  auto_setup?: { source: "youtube" | "instagram"; read_by_ai: boolean; review: string[]; at: string } | null;
  followers: number;
  following: number;
  posts: number;
  median_views: number;
  audience_stage: { id: string; label: string };
  reels: Reel[];
  provenance: Record<string, Provenance>;
  provenance_default: Provenance;
  income_goal: { monthly: number; types: string[] };
  current_rate: number | null;
  best_deal: number | null;
  expertise: string | null;
  discoverable: boolean;
}
