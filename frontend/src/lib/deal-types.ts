export type Stage = "offer" | "contract" | "escrow_funded" | "live" | "verified" | "paid" | "declined";

export interface DealAction {
  id: string;
  label: string;
  kind: "primary" | "secondary" | "ghost";
  needs?: "amount" | "url" | "payment";
}

export interface DealAlert {
  kind: "low_offer" | "verify_late" | "verify_window";
  text: string;
  detail?: string;
  fair?: number;
}

export interface Deal {
  id: string;
  kind: "single" | "collective";
  stage: Stage;
  amount: number;
  fair_total: number | null;
  deliverables: string;
  usage_rights_days: number;
  exclusivity_days: number;
  message: string | null;
  creator: { id: string; name: string; handle: string; avatar_hue: number; is_reference: boolean; upi: string | null };
  brand: { id: string; name: string; hue: number; verified: boolean };
  listing: { id: string; title: string } | null;
  steps: { key: string; label: string; status: "done" | "current" | "upcoming"; at: string | null }[];
  timeline: { stage: string; at: string; note: string }[];
  counter: { amount: number; by: string; at: string; note: string | null; accepted_at?: string; declined_at?: string } | null;
  contract: {
    signed_by_creator?: string | null;
    signed_by_brand?: string | null;
    creator_signature?: string;
    brand_signature?: string;
    terms: string[];
  } | null;
  escrow: { mode: string; ref: string; funded_at: string; amount?: number; collective?: boolean } | null;
  proof_url: string | null;
  verify_due: string | null;
  auto_release_on: string | null;
  verification: { source: string; checked_at: string; views_so_far: number; checks: { label: string; ok: boolean }[]; auto?: boolean } | null;
  payouts: { creator_id: string; amount: number; upi: string; utr: string; at: string }[];
  invoice: { id: string; number: string; status: string } | null;
  alerts: DealAlert[];
  collective: { id: string; size: number; total: number; funded: boolean; split: number | null } | null;
  actions: DealAction[];
  payments_mode: "razorpay-test" | "simulated";
}

export interface DealRow {
  id: string;
  kind: "single" | "collective";
  stage: Stage;
  amount: number;
  fair_total: number | null;
  deliverables: string;
  creator: Deal["creator"];
  brand: Deal["brand"];
  listing: Deal["listing"];
  alerts: DealAlert[];
  actions: string[];
  updated: string | null;
  collective: Deal["collective"];
  counter: Deal["counter"];
}

export interface CollectiveView {
  id: string;
  brand: { id: string; name: string };
  listing: { id: string; title: string };
  total: number;
  combined_reach: number | null;
  funded: boolean;
  escrow: { mode: string; ref: string; funded_at: string } | null;
  paid_out: number;
  refunded: number;
  members: {
    creator_id: string;
    name: string;
    handle: string;
    avatar_hue: number;
    is_reference: boolean;
    price: number;
    split: number;
    deal_id: string;
    stage: Stage;
    proof_url: string | null;
    paid: boolean;
  }[];
  stages: Record<string, number>;
  created_at: string;
  payments_mode: "razorpay-test" | "simulated";
}

export const STAGE_LABEL: Record<Stage, string> = {
  offer: "Offer",
  contract: "Contract",
  escrow_funded: "Escrow funded",
  live: "Post live",
  verified: "Verified",
  paid: "Paid",
  declined: "Declined",
};
