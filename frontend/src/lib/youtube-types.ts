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

export interface WorthReport {
  channel: YouTubeChannel;
  videos: YouTubeVideo[];
  niche: string;
  niche_label: string;
  niche_guessed: boolean;
  prices: { shorts: FormatPrice; long: FormatPrice };
  notes: string[];
  source: "youtube_api";
  fetched_at: string;
}

export interface PlatformStatus {
  platform: "instagram" | "youtube";
  label: string;
  status: "connected" | "linked" | "not_connected" | "unavailable" | "expired" | "error";
  detail: string;
  source?: string;
  fetched_at?: string | null;
}

export interface LinkedYouTube {
  linked: boolean;
  status: PlatformStatus;
  channel?: YouTubeChannel & { source: string; fetched_at: string };
  videos?: YouTubeVideo[];
  prices?: { shorts: FormatPrice; long: FormatPrice };
  niche_label?: string;
  source?: string;
  fetched_at?: string;
}
