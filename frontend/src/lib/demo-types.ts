import type { CreatorSummary, Durable, Move, MoneyPath, RateGap, Roadmap, Stage, TrustInfo } from "./api-types";
import type { Opportunity } from "./market-types";
import type { Estimate, Why } from "./types";

export interface CompareSide {
  creator: CreatorSummary;
  context: { followers: number; median_views: number; has_reels: boolean; reach_ratio: number | null; trust: TrustInfo | null };
  stage: Stage;
  rate_gap: RateGap;
  fair: {
    range: { low: number; high: number };
    per_reel: number;
    follower_price: number;
    lister_name: string | null;
    uplift_vs_followers: number | null;
    estimate: Estimate;
    why: Why;
  };
  durable: Durable;
  roadmap: Pick<Roadmap, "working" | "gaps" | "skills">;
  paths: MoneyPath[];
  goal: { goal: number; top3: Estimate; reachable: boolean };
  opportunities: Omit<Opportunity, "scopes" | "scope_source" | "application">[];
  moves: Move[];
}

export type GuideStepId = "who" | "stage" | "price" | "roadmap" | "money" | "opportunities" | "moves";

export interface GuideStep {
  id: GuideStepId;
  title: string;
  caption: string;
  route: string;
}

export interface Compare {
  a: CompareSide;
  b: CompareSide;
  guide: GuideStep[];
}
