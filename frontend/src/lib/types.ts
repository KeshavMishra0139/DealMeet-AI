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
  role: "creator" | "brand";
  title: string;
  subtitle: string;
  tag: string;
}

export interface Health {
  status: string;
  today: string;
  modes: { db: string; ai: string; payments: string; auth: string };
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
