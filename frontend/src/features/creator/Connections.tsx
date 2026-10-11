import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Instagram, Link2, RefreshCw, ShieldCheck, Trash2, Youtube } from "lucide-react";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ShareBars, type ShareRow } from "@/components/charts/ShareBars";
import { toast } from "sonner";
import { ErrorState, SectionTitle } from "@/components/shared/Bits";
import { ChannelAvatar } from "@/components/shared/ChannelAvatar";
import { FormatPriceCard } from "@/components/shared/FormatPriceCard";
import { SourceBadge } from "@/components/shared/SourceBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Label, Skeleton } from "@/components/ui/form";
import { Dialog, DialogContent } from "@/components/ui/overlays";
import { useI18n } from "@/i18n";
import { api, post } from "@/lib/api";
import { count } from "@/lib/format";
import { useCreatorId } from "@/lib/session";
import type { InstagramAccount, InstagramData, LinkedYouTube, PlatformStatus } from "@/lib/youtube-types";

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
        <InstagramCard creatorId={id} status={by.instagram} />
      </div>
    </div>
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

const AGE_ORDER = ["13-17", "18-24", "25-34", "35-44", "45-54", "55-64", "65+"];

function shares(counts: Record<string, number> | undefined, order?: string[], top = 6): ShareRow[] {
  const entries = Object.entries(counts ?? {});
  const total = entries.reduce((a, [, v]) => a + v, 0) || 1;
  const rows = entries.map(([k, v]) => ({ label: k.split(",")[0], share: v / total }));
  if (order) return rows.filter((r) => order.includes(r.label)).sort((a, b) => order.indexOf(a.label) - order.indexOf(b.label));
  return rows.sort((a, b) => b.share - a.share).slice(0, top);
}

function InstagramCard({ creatorId, status }: { creatorId: string; status: PlatformStatus }) {
  const qc = useQueryClient();
  const [params, setParams] = useSearchParams();
  const [consent, setConsent] = useState(false);
  const [confirmOff, setConfirmOff] = useState(false);
  const available = status.status !== "unavailable";
  const q = useQuery({ queryKey: ["instagram", creatorId], queryFn: () => api<InstagramData>(`/creators/${creatorId}/instagram`), enabled: available });

  // Instagram sends the browser back with ?ig=connected or ?ig=error&msg=...
  useEffect(() => {
    const result = params.get("ig");
    if (!result) return;
    const msg = params.get("msg");
    if (result === "connected") toast.success("Instagram connected", { description: msg ?? "Your numbers are now labelled Live data." });
    else toast.error("Instagram wasn't connected", { description: msg ?? "Try again from here." });
    params.delete("ig");
    params.delete("msg");
    setParams(params, { replace: true });
  }, [params, setParams]);

  const start = useMutation({
    mutationFn: () => api<{ url: string }>("/connect/instagram/start?json=1"),
    onSuccess: ({ url }) => window.location.assign(url),
    onError: (e) => toast.error((e as Error).message),
  });
  const refresh = (d: InstagramData) => {
    qc.setQueryData(["instagram", creatorId], d);
    void qc.invalidateQueries({ predicate: (x) => x.queryKey[0] !== "instagram" });
  };
  const sync = useMutation({
    mutationFn: () => post<InstagramData>("/connect/instagram/sync"),
    onSuccess: (d) => {
      refresh(d);
      toast.success("Instagram synced");
    },
    onError: (e) => toast.error((e as Error).message),
  });
  const disconnect = useMutation({
    mutationFn: () => post<InstagramData>("/connect/instagram/disconnect"),
    onSuccess: (d) => {
      setConfirmOff(false);
      refresh(d);
      toast.success("Instagram disconnected", { description: "The access token and all Instagram data were deleted from JodiDar." });
    },
  });
  const acct = q.data?.account;
  const st = q.data?.status ?? status;

  return (
    <section aria-labelledby="pc-instagram" className="card-surface rounded-[var(--radius-card)] p-5">
      <div className="flex flex-wrap items-center gap-3">
        <Instagram className="size-5" aria-hidden />
        <h2 id="pc-instagram" className="flex-1 font-display text-lg font-semibold">
          Instagram
        </h2>
        <StatusChip status={st.status} />
      </div>
      <p className="mt-2 text-sm text-fg-2">{st.detail}</p>

      {available && (st.status === "not_connected" || st.status === "expired") && (
        <Button className="mt-4" variant="primary" onClick={() => setConsent(true)}>
          <Instagram aria-hidden /> {st.status === "expired" ? "Reconnect Instagram" : "Connect Instagram"}
        </Button>
      )}

      {acct && st.status !== "not_connected" && <InstagramSummary acct={acct} />}

      {acct && (
        <div className="mt-4 flex flex-wrap gap-2">
          <Button size="sm" variant="outline" loading={sync.isPending} onClick={() => sync.mutate()}>
            {!sync.isPending && <RefreshCw aria-hidden />} Sync now
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setConfirmOff(true)}>
            <Trash2 aria-hidden /> Disconnect
          </Button>
        </div>
      )}

      <Dialog open={consent} onOpenChange={setConsent}>
        <DialogContent title="Connect Instagram" description="Official Instagram login. Read-only.">
          <p className="rounded-2xl border border-line bg-surface-2 p-4 text-sm leading-relaxed">{q.data?.consent}</p>
          <p className="mt-3 flex gap-2 text-xs text-muted">
            <ShieldCheck className="size-4 shrink-0 text-success" aria-hidden />
            Your account must be a Creator or Business account. While the JodiDar app is in development mode, only accounts added as Instagram
            Testers can connect.
          </p>
          <div className="mt-5 flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setConsent(false)}>
              Cancel
            </Button>
            <Button variant="primary" loading={start.isPending} onClick={() => start.mutate()}>
              Continue to Instagram
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={confirmOff} onOpenChange={setConfirmOff}>
        <DialogContent title="Disconnect Instagram?" description="JodiDar deletes the access token and every Instagram post, insight and audience number it stored.">
          <div className="mt-2 flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setConfirmOff(false)}>
              Keep connected
            </Button>
            <Button variant="primary" loading={disconnect.isPending} onClick={() => disconnect.mutate()}>
              Disconnect and delete
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </section>
  );
}

function InstagramSummary({ acct }: { acct: InstagramAccount }) {
  const g = acct.demographics?.gender;
  const gTotal = (g?.F ?? 0) + (g?.M ?? 0);
  const age = shares(acct.demographics?.age, AGE_ORDER);
  const cities = shares(acct.demographics?.city);
  return (
    <div className="mt-4 space-y-4">
      <div className="flex flex-wrap items-center gap-3 rounded-2xl bg-surface-2 p-3.5">
        <ChannelAvatar src={acct.picture} name={acct.username ?? "Instagram"} size={40} />
        <div className="min-w-[180px] flex-1">
          <p className="flex flex-wrap items-center gap-2 font-medium">
            @{acct.username} <SourceBadge source={acct.source} fetchedAt={acct.fetched_at} />
          </p>
          <p className="text-xs text-muted">
            {count(acct.followers)} followers
            {acct.reach_28d != null && ` · ${count(acct.reach_28d)} reached in 28 days`}
            {acct.views_28d != null && ` · ${count(acct.views_28d)} views in 28 days`}
          </p>
        </div>
      </div>
      {age.length > 0 || cities.length > 0 ? (
        <div className="grid gap-4 md:grid-cols-2">
          {age.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold">Followers by age</h3>
              {gTotal > 0 && (
                <p className="mt-0.5 text-xs text-muted">
                  {Math.round(((g?.F ?? 0) / gTotal) * 100)}% women, {Math.round(((g?.M ?? 0) / gTotal) * 100)}% men
                </p>
              )}
              <div className="mt-2">
                <ShareBars rows={age} caption="Instagram followers by age" />
              </div>
            </div>
          )}
          {cities.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold">Top cities</h3>
              <div className="mt-2">
                <ShareBars rows={cities} caption="Instagram followers by city" />
              </div>
            </div>
          )}
        </div>
      ) : null}
      {acct.notes.length > 0 && (
        <ul className="space-y-1 text-xs text-muted">
          {acct.notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
