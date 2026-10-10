export interface Kit {
  creator_id: string;
  name: string;
  handle: string;
  avatar_hue: number;
  is_reference: boolean;
  reference_note: string | null;
  niche: string;
  languages: string[];
  location: string | null;
  copy: { headline: string; bio: string };
  copy_source: "ai" | "cache" | "template";
  stats: { label: string; value: string; simulated: boolean }[] | null;
  formats: { topic: string; views: string; simulated: boolean }[] | null;
  audience: { line: string; simulated: boolean } | null;
  rates: { label: string; value: string }[] | null;
  /** Null when the creator hides rates on the public page. */
  from_rate: number | null;
  trust: { score: number; level: "high" | "medium" | "low"; reasons: string[] } | null;
  safety_note: string;
  public?: { stats: boolean; demographics: boolean; rates: boolean };
  link: string;
  path: string;
  generated_on: string;
  has_simulated: boolean;
}
