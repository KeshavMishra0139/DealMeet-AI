import { Database, PenLine, Radio } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { shortDate, timeOfDay } from "@/lib/format";

/** Where a number comes from. Every creator, brand, post and metric record carries one. */
export type DataSource = "youtube_api" | "instagram_api" | "manual" | "synthetic";

const LABEL: Record<DataSource, string> = {
  youtube_api: "Live data",
  instagram_api: "Live data",
  manual: "Self-reported",
  synthetic: "Sample data",
};

const LABEL_HI: Record<DataSource, string> = {
  youtube_api: "लाइव डेटा",
  instagram_api: "लाइव डेटा",
  manual: "खुद बताया गया",
  synthetic: "सैंपल डेटा",
};

const DETAIL: Record<DataSource, string> = {
  youtube_api: "From YouTube's official API",
  instagram_api: "From Instagram's official API",
  manual: "Typed in by the creator",
  synthetic: "Generated sample data, not real",
};

/** "Live data" for API data, "Self-reported" for typed numbers, "Sample data" for synthetic. */
export function SourceBadge({
  source,
  fetchedAt,
  className,
  lang = "en",
}: {
  source: DataSource | string | null | undefined;
  fetchedAt?: string | null;
  className?: string;
  /** Hindi labels for a Hindi media kit; the app's own language is separate. */
  lang?: "en" | "hi";
}) {
  if (!source || !(source in LABEL)) return null;
  const s = source as DataSource;
  const live = s === "youtube_api" || s === "instagram_api";
  const Icon = live ? Radio : s === "manual" ? PenLine : Database;
  const when = live && fetchedAt ? ` · fetched ${shortDate(fetchedAt)}, ${timeOfDay(fetchedAt)}` : "";
  return (
    <Badge size="sm" variant={live ? "success" : s === "manual" ? "neutral" : "warn"} className={className} title={DETAIL[s] + when}>
      <Icon aria-hidden /> {(lang === "hi" ? LABEL_HI : LABEL)[s]}
      <span className="sr-only">: {DETAIL[s] + when}</span>
    </Badge>
  );
}
