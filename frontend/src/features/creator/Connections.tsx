import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Instagram, Link2, RefreshCw, Trash2, Youtube } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { ErrorState, SectionTitle } from "@/components/shared/Bits";
import { ChannelAvatar } from "@/components/shared/ChannelAvatar";
import { FormatPriceCard } from "@/components/shared/FormatPriceCard";
import { SourceBadge } from "@/components/shared/SourceBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Label, Skeleton } from "@/components/ui/form";
import { useI18n } from "@/i18n";
import { api, post } from "@/lib/api";
import { count } from "@/lib/format";
import { useCreatorId } from "@/lib/session";
import type { LinkedYouTube, PlatformStatus } from "@/lib/youtube-types";

const STATUS_LABEL: Record<PlatformStatus["status"], string> = {
  connected: "Connected",
  linked: "Linked: public data",
  not_connected: "Not connected",
  unavailable: "Not available here",
  expired: "Needs reconnecting",
  error: "Error",
};

export function StatusChip({ status }: { status: PlatformStatus["status"] }) {
  const variant = status === "connected" ? "success" : status === "linked" ? "accent" : status === "expired" || status === "error" ? "warn" : "neutral";
  return (
    <Badge size="sm" variant={variant}>
      {STATUS_LABEL[status]}
    </Badge>
  );
}

export default function Connections() {
  const { t } = useI18n();
  const id = useCreatorId();
  const q = useQuery({ queryKey: ["connections", id], queryFn: () => api<{ platforms: PlatformStatus[]; sample_data: boolean }>(`/creators/${id}/connections`) });
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data) return <Skeleton className="h-96 rounded-[var(--radius-card)]" />;
  const by = Object.fromEntries(q.data.platforms.map((p) => [p.platform, p]));
  return (
    <div>
      <h1 className="font-display text-[26px] font-semibold tracking-tight sm:text-[30px]">{t("connections.title")}</h1>
      <p className="mt-1 max-w-2xl text-[15px] text-fg-2">
        Where your numbers come from. Official logins only, read-only: we never ask for your password, never post for you and never scrape.
      </p>
      {q.data.sample_data && (
        <p className="mt-3 rounded-2xl border border-warn/40 bg-warn-soft p-3 text-sm">
          Your profile uses sample insights from onboarding (demo). Link a real account and its numbers are labelled Live data.
        </p>
      )}
      <div className="mt-6 space-y-5">
        <YouTubeCard creatorId={id} status={by.youtube} />
        <PlatformCard status={by.instagram} icon={Instagram} />
      </div>
    </div>
  );
}

function PlatformCard({ status, icon: Icon }: { status: PlatformStatus; icon: typeof Instagram }) {
  return (
    <section aria-labelledby={`pc-${status.platform}`} className="card-surface rounded-[var(--radius-card)] p-5">
      <div className="flex flex-wrap items-center gap-3">
        <Icon className="size-5" aria-hidden />
        <h2 id={`pc-${status.platform}`} className="flex-1 font-display text-lg font-semibold">
          {status.label}
        </h2>
        <StatusChip status={status.status} />
      </div>
      <p className="mt-2 text-sm text-fg-2">{status.detail}</p>
    </section>
  );
}

function YouTubeCard({ creatorId, status }: { creatorId: string; status: PlatformStatus }) {
  const qc = useQueryClient();
  const [handle, setHandle] = useState("");
  const q = useQuery({ queryKey: ["youtube", creatorId], queryFn: () => api<LinkedYouTube>(`/creators/${creatorId}/youtube`), enabled: status.status !== "unavailable" });
  const done = (d: LinkedYouTube) => {
    qc.setQueryData(["youtube", creatorId], d);
    void qc.invalidateQueries({ queryKey: ["connections", creatorId] });
  };
  const link = useMutation({
    mutationFn: (h: string) => post<LinkedYouTube>(`/creators/${creatorId}/youtube/link`, { handle: h }),
    onSuccess: (d) => {
      done(d);
      toast.success("Channel linked", { description: "Your public YouTube numbers are now labelled Live data." });
    },
    onError: (e) => toast.error((e as Error).message),
  });
  const unlink = useMutation({
    mutationFn: () => api<LinkedYouTube>(`/creators/${creatorId}/youtube/link`, { method: "DELETE" }),
    onSuccess: (d) => {
      done(d);
      toast.success("Channel unlinked", { description: "Its videos and snapshots were deleted from JodiDar." });
    },
  });
  const d = q.data;

  return (
    <section aria-labelledby="pc-youtube" className="card-surface rounded-[var(--radius-card)] p-5">
      <div className="flex flex-wrap items-center gap-3">
        <Youtube className="size-5" aria-hidden />
        <h2 id="pc-youtube" className="flex-1 font-display text-lg font-semibold">
          YouTube
        </h2>
        <StatusChip status={status.status} />
      </div>
      <p className="mt-2 text-sm text-fg-2">{status.detail}</p>

      {status.status !== "unavailable" && d && !d.linked && (
        <form
          className="mt-4 flex flex-wrap items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            link.mutate(handle);
          }}
        >
          <div className="min-w-[220px] flex-1">
            <Label htmlFor="yt-handle">Your channel's @handle or link</Label>
            <Input id="yt-handle" value={handle} onChange={(e) => setHandle(e.target.value)} placeholder="@yourchannel" required />
          </div>
          <Button type="submit" variant="primary" loading={link.isPending}>
            {!link.isPending && <Link2 aria-hidden />} Link channel
          </Button>
        </form>
      )}

      {d?.linked && d.channel && (
        <div className="mt-4 space-y-4">
          <div className="flex flex-wrap items-center gap-3 rounded-2xl bg-surface-2 p-3.5">
            <ChannelAvatar src={d.channel.thumbnail} name={d.channel.title} size={40} />
            <div className="min-w-[180px] flex-1">
              <p className="flex flex-wrap items-center gap-2 font-medium">
                {d.channel.title} <SourceBadge source={d.channel.source} fetchedAt={d.channel.fetched_at} />
                {!d.channel.ownership_verified && (
                  <Badge size="sm" variant="outline">
                    Ownership not verified
                  </Badge>
                )}
              </p>
              <p className="text-xs text-muted">
                {d.channel.handle} · {d.channel.subscribers == null ? "subscribers hidden" : `${count(d.channel.subscribers)} subscribers`} ·{" "}
                {count(d.channel.video_count)} videos
              </p>
            </div>
            <div className="flex w-full gap-2 sm:w-auto">
              <Button size="sm" variant="outline" loading={link.isPending} onClick={() => link.mutate(d.channel?.handle ?? d.channel?.channel_id ?? "")}>
                {!link.isPending && <RefreshCw aria-hidden />} Refresh
              </Button>
              <Button size="sm" variant="ghost" loading={unlink.isPending} onClick={() => unlink.mutate()}>
                {!unlink.isPending && <Trash2 aria-hidden />} Unlink
              </Button>
            </div>
          </div>
          {d.prices && (
            <>
              <SectionTitle id="yt-prices" eyebrow={`Priced for ${d.niche_label?.toLowerCase()}`} title="What a brand video is worth" />
              <div className="grid gap-4 md:grid-cols-2">
                <FormatPriceCard price={d.prices.shorts} title="One brand Short" />
                <FormatPriceCard price={d.prices.long} title="One brand integration in a long video" />
              </div>
              <p className="text-xs text-muted">Refreshing uses YouTube's numbers from the last 12 hours at most.</p>
            </>
          )}
        </div>
      )}
    </section>
  );
}
