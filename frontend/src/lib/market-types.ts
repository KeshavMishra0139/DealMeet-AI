import type { Estimate, Why } from "./types";
import type { TrustInfo } from "./api-types";

export type ListingType = "brand_campaign" | "pr_service" | "page" | "creator_collab" | "collective";
export type Scopes = { stats: boolean; demographics: boolean; rate_card: boolean };
/** Brand-safety notes as brands see them: the flag and the fix suggested to the creator. */
export interface Safety {
  flags: { id: string; label: string; fix: string }[];
}

export interface Opportunity {
  id: string;
  type: ListingType;
  type_label: string;
  title: string;
  summary: string;
  lister: { id: string; name: string; kind: string; hue: number; verified: boolean };
  niches: string[];
  languages: string[];
  regions: string[];
  deal_kind: string;
  deliverables: { kind: string; count: number }[];
  usage_rights_days: number;
  deadline: string | null;
  collective_size: number | null;
  budget: Record<string, number>;
  fit: number;
  applied: boolean;
  value: { kind: string; estimate: Estimate | null; budget_below_fair?: boolean };
  fair_total: number | null;
  why: Why;
  scopes: Scopes;
  scope_source: "grant" | "default";
  application: "applied" | "opted_in" | "withdrawn" | null;
}

export interface Opportunities {
  items: Opportunity[];
  hidden: { id: string; title: string; reasons: string[] }[];
  counts: Record<string, number>;
}

export interface Privacy {
  discoverable: boolean;
  defaults: Scopes;
  scope_labels: Record<keyof Scopes, string>;
  grants: {
    lister_id: string;
    lister: string;
    kind: string;
    verified: boolean;
    scopes: Scopes;
    status: "active" | "revoked";
    granted_at: string | null;
    revoked_at: string | null;
  }[];
  requests: { id: string; lister_id: string; lister: string; scopes: string[]; at: string }[];
  audit: { id: string; lister: string; action: string; scopes: string[]; at: string; actor: string }[];
  sources: { platform: string; connected: boolean; via: string | null }[];
  is_reference: boolean;
}

export interface BrandMatch {
  id: string;
  name: string;
  handle: string;
  avatar_hue: number;
  is_reference: boolean;
  reference_note: string | null;
  niche_label: string;
  languages: string[];
  location: string | null;
  audience_stage: string;
  followers: number | null;
  median_views: number | null;
  engagement: number | null;
  fit: number;
  rank: number;
  reasons: string[];
  cautions: string[];
  trust: TrustInfo | null;
  safety?: Safety;
  fair: { range: { low: number; high: number }; total: number; per_reel: number; deliverables: string };
  within_budget: boolean;
  rate_card: number | null;
  scopes: Scopes;
  application: string | null;
  deal_stage: string | null;
}

export interface Matches {
  listing_id: string;
  summary: string;
  detail: string;
  items: BrandMatch[];
  total: number;
}

export interface CollectiveMember {
  id: string;
  name: string;
  handle: string;
  avatar_hue: number;
  is_reference: boolean;
  niche_label: string;
  language: string;
  city: string;
  audience_stage: string;
  /** Reach, followers and engagement are null when the creator doesn't share stats with this brand. */
  followers: number | null;
  reach: number | null;
  effective_reach: number | null;
  /** Exact overlap only when both creators share demographics; otherwise just the level. */
  overlap: number | null;
  overlap_level: "High" | "Low";
  overlap_with: string | null;
  price: number;
  split: number;
  fit: number;
  trust: TrustInfo | null;
  engagement: number | null;
  opted_in: boolean;
}

export interface Collective {
  listing_id: string;
  budget: number;
  size: number;
  size_target: number | null;
  total: number;
  remaining: number;
  /** Pack totals are null unless every member shares stats with this brand. */
  combined_reach: number | null;
  raw_reach: number | null;
  dedup_saved: number | null;
  avg_engagement: number | null;
  cost_per_1k: number | null;
  trust_min: number;
  members: CollectiveMember[];
  excluded: { id: string; name: string; reason: string }[];
  notes: string[];
  summary: string;
}

export interface Listing {
  id: string;
  type: ListingType;
  owner_id: string;
  owner: { id: string; name: string; hue: number } | null;
  title: string;
  summary: string;
  niches: string[];
  niche_labels: string[];
  languages: string[];
  language_labels: string[];
  regions: string[];
  deal_kind: string;
  deliverables: { kind: string; count: number }[];
  usage_rights_days: number;
  exclusivity_days: number;
  min_followers: number;
  budget: Record<string, number>;
  collective_size: number | null;
  deadline: string | null;
  posted_on: string | null;
  status: string;
}

export interface Console {
  brand: { id: string; name: string; category: string; hue: number };
  headline: string;
  campaigns: {
    id: string;
    title: string;
    type: ListingType;
    deal_kind: string;
    status: string;
    deadline: string | null;
    posted_on: string | null;
    languages: string[];
    budget: Record<string, number>;
    collective_size: number | null;
    candidates: number;
    applications: number;
    deals: number;
    committed: number;
  }[];
  escrow: { held: number; count: number; items: { deal_id: string; creator: string; amount: number; stage: string; stage_label: string }[] };
  paid_total: number;
  stages: { stage: string; label: string; count: number; amount: number }[];
  needs_you: { deal_id: string; kind: string; text: string; detail: string; urgent: boolean }[];
  recent: {
    deal_id: string;
    creator: string;
    creator_id: string;
    avatar_hue: number;
    is_reference: boolean;
    amount: number;
    stage: string;
    stage_label: string;
    kind: string;
    updated: string;
  }[];
}
