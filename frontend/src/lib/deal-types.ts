export type Stage = "offer" | "contract" | "escrow_funded" | "live" | "verified" | "paid" | "declined";

export interface DealAction {
  id: string;
  label: string;
  kind: "primary" | "secondary" | "ghost";
  needs?: "amount" | "url" | "payment" | "note";
}

export interface DealAlert {
  kind: "low_offer" | "verify_late" | "verify_window" | "revision" | "payout_not_connected";
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
  creator: { id: string; name: string; handle: string; avatar_hue: number; is_reference: boolean };
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
  verification: (PostCheck & { auto?: boolean; approved_by?: "brand" | "auto"; approved_at?: string }) | null;
  post_check: PostCheck | null;
  /** Views expected when the offer was accepted, for the case study. */
  predicted: { views: number; basis: string; source: string; at: string } | null;
  /** The creator's own view count after the deal (self-reported). */
  result: { views: number; source: "manual"; at: string } | null;
  rating: { stars: number; note: string | null; at: string } | null;
  revisions: { reason: string; at: string; post: string | null }[];
  payout: { status: "simulated" | "not_connected" | "paid"; at: string } | null;
  payouts: { creator_id: string; amount: number; mode: "simulated" | "provider"; at: string }[];
  invoice: { id: string; number: string; status: string } | null;
  alerts: DealAlert[];
  collective: { id: string; size: number; total: number; funded: boolean; split: number | null } | null;
  actions: DealAction[];
  payments_mode: PaymentsMode;
  payout_mode: "simulated" | "not_connected";
}

export type PaymentsMode = "razorpay-test" | "simulated" | "not_connected";

/** Automatic checks of a submitted post. Without a connected account every check is "not_checked". */
export interface PostCheck {
  source: string;
  checked_at: string | null;
  note?: string;
  checks: { label: string; status: "passed" | "failed" | "not_checked"; detail?: string }[];
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
  paid_out: number | null;
  refunded: number | null;
  members: {
    creator_id: string;
    name: string;
    handle: string;
    avatar_hue: number;
    is_reference: boolean;
    price: number | null;
    split: number | null;
    deal_id: string | null;
    stage: Stage;
    proof_url: string | null;
    paid: boolean;
  }[];
  stages: Record<string, number>;
  created_at: string;
  payments_mode: PaymentsMode;
}

export const STAGE_LABEL: Record<Stage, string> = {
  offer: "Offer",
  contract: "Contract",
  escrow_funded: "Escrow funded",
  live: "Post submitted",
  verified: "Approved",
  paid: "Paid out",
  declined: "Declined",
};
