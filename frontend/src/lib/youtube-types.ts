import type { Estimate } from "./types";

export interface FormatPrice {
  format: "shorts" | "long";
  enough_data: boolean;
  videos: number;
  reason?: string;
  median_views?: number;
  per_video?: number;
  estimate?: Estimate;
  why?: string[];
  /** The price before the AI market review, when one was applied. */
  formula_per_video?: number;
  ai?: { adjust_pct: number; reasons: string[]; confidence: "low" | "medium" | "high" };
}

export interface YouTubeVideo {
  post_id: string;
  title: string;
  published_at: string;
  views: number;
  format: "shorts" | "long";
  permalink: string;
}

export interface YouTubeChannel {
  id?: string;
  channel_id?: string;
  title: string;
  handle: string | null;
  thumbnail: string | null;
  subscribers: number | null;
  subscribers_hidden: boolean;
  total_views: number;
  video_count: number;
  ownership_verified?: boolean;
  analytics_connected?: boolean;
}

export interface PlatformStatus {
  platform: "instagram" | "youtube";
  label: string;
  status: "connected" | "linked" | "not_connected" | "unavailable" | "expired" | "error";
  detail: string;
  source?: string;
  fetched_at?: string | null;
}

export interface YouTubeAnalytics {
  period_days: number;
  start: string;
  end: string;
  views: number;
  minutes_watched: number;
  average_view_duration_s: number;
  age_gender: { age: string; gender: string; percent: number }[];
  countries: { country: string; views: number }[];
  source: "youtube_api";
  fetched_at: string;
}

export interface LinkedYouTube {
  analytics?: YouTubeAnalytics | null;
  analytics_consent?: string;
  linked: boolean;
  status: PlatformStatus;
  channel?: YouTubeChannel & { source: string; fetched_at: string };
  videos?: YouTubeVideo[];
  prices?: { shorts: FormatPrice; long: FormatPrice };
  niche_label?: string;
  source?: string;
  fetched_at?: string;
}

export interface InstagramAccount {
  ig_user_id: string;
  username: string | null;
  account_type: string | null;
  followers: number;
  media_count: number | null;
  picture: string | null;
  reach_28d: number | null;
  views_28d: number | null;
  demographics: { age?: Record<string, number>; gender?: Record<string, number>; city?: Record<string, number>; country?: Record<string, number> } | null;
  notes: string[];
  source: "instagram_api";
  fetched_at: string;
}

export interface InstagramData {
  status: PlatformStatus;
  consent: string;
  account: InstagramAccount | null;
  posts: { post_id: string; caption: string; permalink: string; published_at: string; views: number | null; likes: number | null; media_product_type: string }[];
}
