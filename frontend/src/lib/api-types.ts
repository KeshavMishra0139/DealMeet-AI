// Shapes returned by the creator API (see backend/app/routers/creators.py).
import type { Estimate, Why } from "./types";

export interface CreatorSummary {
  id: string;
  handle: string;
  name: string;
  avatar_hue: number;
  niche: string;
  niche_label: string;
  languages: string[];
  language_labels: string[];
  city: string | null;
  region: string | null;
  followers: number;
  median_views: number;
  audience_stage: { id: string; label: string };
  is_reference: boolean;
  reference_note: string | null;
  income_goal: { monthly: number; types: string[] } | null;
}

export interface Stage {
  id: string;
  label: string;
  line: string;
  audience_stage: { id: string; label: string };
  why: Why;
  hi?: { label: string; line: string };
}

export type Effort = "S" | "M" | "L";
export type MoveCategory = "money" | "growth" | "opportunity";

export interface Move {
  id: string;
  kind: string;
  category: MoveCategory;
  title: string;
  reason: string;
  impact: Estimate;
  effort: Effort;
  effort_hint: string;
  why: Why;
  cta: { label: string; to: string };
  status: "open" | "done" | "skipped";
  outcome: { result: "worked" | "partly" | "no" | null; amount: number | null; note: string | null } | null;
  carried_over?: boolean;
  follow_up_of?: string;
  order: number;
  hi?: { title: string; reason: string };
}

export interface Plan {
  id: string;
  week: number;
  week_start: string;
  moves: Move[];
  changes: string[];
  done_count: number;
}

export interface Durable {
  score: number | null;
  state: "scored" | "no_income";
  headline: string;
  sources: { source: string; label: string; amount: number; share: number }[];
  warning: string | null;
  warning_hi?: string | null;
  next_stream: { type: string; title: string; estimate: Estimate; first_step: string } | null;
  monthly_avg?: number;
  why: Why;
}

export interface RateGap {
  fair: { low: number; high: number };
  per_reel: number;
  current: number | null;
  follower_price: number;
  gap: number | null;
  line: string;
  line_hi?: string;
  brand: string | null;
  why: Why;
}

export interface PipelineItem {
  id: string;
  brand: string;
  amount: number;
  stage: string;
  below_pct?: number;
  fair_total?: number;
}

export interface Alert {
  kind: "low_offer" | "verify_late" | "invoice_late";
  text: string;
  detail: string;
  deal_id?: string;
  invoice_id?: string;
  hi?: { text: string; detail: string };
}

export interface Pipeline {
  offers: PipelineItem[];
  active: PipelineItem[];
  awaiting: PipelineItem[];
  awaiting_total: number;
  alerts: Alert[];
}

export interface TrustInfo {
  score: number;
  level: "high" | "medium" | "low";
  reasons: string[];
  method: string;
  /** Inputs that are sample data, e.g. ["follower history"]. */
  simulated?: string[];
}

export interface Home {
  creator: CreatorSummary;
  stage: Stage;
  plan: Plan;
  durable: Durable;
  rate_gap: RateGap;
  pipeline: Pipeline;
  context: {
    followers: number;
    median_views: number;
    has_reels: boolean;
    reach_ratio: number | null;
    trust: TrustInfo | null;
    recent?: { date: string; views: number }[];
    recent_provenance?: { views: string; followers: string };
  };
}

export interface PriceStep {
  key: string;
  label: string;
  pct: number | null;
  amount: number;
  reason: string;
  capped?: boolean;
  cap?: [number, number];
  simulated: boolean;
  simulated_fields?: string[];
  estimated?: boolean;
}

export interface FairPrice {
  /** What the price is built from: "Estimate from Instagram data", "... from sample data", ... */
  data_label?: string;
  data_source?: "instagram_api" | "youtube_api" | "manual" | "synthetic";
  creator_id: string;
  lister_id: string | null;
  lister_name: string | null;
  deliverables: string;
  base: number;
  per_reel: number;
  total: number;
  range: { low: number; high: number };
  steps: PriceStep[];
  follower_price: number;
  follower_rate: number;
  uplift_vs_followers: number | null;
  estimate: Estimate;
  why: Why;
  model_check?: { predicted: number; agrees_within_pct: number; trained_on: number; note: string; checked_before_floor?: boolean };
}

export interface MoneyPath {
  type: string;
  title: string;
  fit: number;
  fit_score: number;
  effort: Effort;
  estimate: Estimate;
  reasons: string[];
  first_step: string;
  listing_id?: string;
  score: number;
  rank: number;
  active: boolean;
  why: Why;
}

export interface Money {
  creator: CreatorSummary;
  stage: Stage;
  fair: FairPrice;
  brand_options: { id: string; name: string; category: string; fit: number }[];
  paths: MoneyPath[];
  goal: { goal: number; top3: Estimate; reachable: boolean };
  durable: Durable;
  rate_gap: RateGap;
}

export interface Gap {
  id: string;
  title: string;
  kind: "topic" | "format";
  evidence: string[];
  why: Why;
}

export interface Roadmap {
  creator: CreatorSummary;
  stage: Stage;
  working: { topic: string; median_views: number; count: number; save_rate: number; why: Why }[];
  gaps: Gap[];
  skills: { rank: number; title: string; action: string; reason: string }[];
  twins: { id: string; name: string; followers: number; platform: string; languages: string[]; steps: string[]; lesson: string; label: string }[];
  topics: { language: string; ideas: { native: string; english: string; why: string }[]; source: "ai" | "cache" | "template" };
  plan: { week: number; title: string; items: { kind: string; title: string }[] }[];
}

/** GET /creators/{id}/weekly-report (backend services/weekly_report.py). "dealmeet": the app's own records. */
export type WeeklySource = "dealmeet" | "synthetic" | "manual" | "instagram_api" | "youtube_api";

export interface WeeklyReport {
  week: { start: string; end: string; previous_start: string };
  profile_views: { this: number; last: number; brands: number; source: WeeklySource };
  offers: { this: number; last: number; value: number; last_value: number; source: WeeklySource };
  paid: { this: number; last: number; deals: number; simulated: boolean; source: WeeklySource };
  /** Null when the creator has no reels at all. */
  reach: { this: number; last: number; reels: number; last_reels: number; source: WeeklySource } | null;
  followers: { platform: "instagram" | "youtube"; now: number; before: number; source: WeeklySource }[];
  quiet: boolean;
}
