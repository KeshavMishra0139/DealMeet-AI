// Connections: which apps are connected, at a glance. One row per app with a status dot
// (green live, amber needs reconnecting, red a problem, grey not connected), then Help, where
// a creator can also remove an app's access after an "Are you sure?". The numbers themselves
// live on Home and Money.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Instagram, Link2, RefreshCw, ShieldCheck, Youtube } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { useLoadWipe, ConnectionsSkeleton } from "@/components/shared/Skeletons";
import { ErrorState } from "@/components/shared/Bits";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/form";
import { Dialog, DialogContent } from "@/components/ui/overlays";
import { useI18n } from "@/i18n";
import { api, post } from "@/lib/api";
import { firebaseEnabled, firebaseMessage, youtubeAnalyticsToken } from "@/lib/firebase";
import { useCreatorId } from "@/lib/session";
import { cn } from "@/lib/utils";
import type { InstagramData, LinkedYouTube, PlatformStatus } from "@/lib/youtube-types";

type Status = PlatformStatus["status"];

const STATUS: Record<Status, { label: string; dot: string; text: string }> = {
  connected: { label: "Live", dot: "bg-success", text: "text-success" },
  linked: { label: "Live", dot: "bg-success", text: "text-success" },
  expired: { label: "Reconnect needed", dot: "bg-warn", text: "text-warn" },
  error: { label: "Connection problem", dot: "bg-danger", text: "text-danger" },
  not_connected: { label: "Not connected", dot: "bg-muted", text: "text-muted" },
  unavailable: { label: "Not available here", dot: "bg-muted", text: "text-muted" },
};

/** A status dot and its label (green live, amber reconnect, red problem, grey off). */
export function StatusChip({ status }: { status: Status }) {
  const s = STATUS[status];
  const live = status === "connected" || status === "linked";
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-xs font-medium", s.text)}>
      <span className="relative flex size-2">
        {live && <span className={cn("absolute inline-flex size-full animate-ping rounded-full opacity-60 motion-reduce:hidden", s.dot)} />}
        <span className={cn("relative inline-flex size-2 rounded-full", s.dot)} />
      </span>
      {s.label}
    </span>
  );
}

function when(iso?: string | null) {
  if (!iso) return null;
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

export default function Connections() {
  const { t } = useI18n();
  const id = useCreatorId();
  const q = useQuery({ queryKey: ["connections", id], queryFn: () => api<{ platforms: PlatformStatus[]; sample_data: boolean }>(`/creators/${id}/connections`) });
  const ready = useLoadWipe(!!q.data);
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data || !ready) return <ConnectionsSkeleton />;
  const by = Object.fromEntries(q.data.platforms.map((p) => [p.platform, p]));
  return (
    <div>
      <h1 className="font-display text-[26px] font-semibold tracking-tight sm:text-[30px]">{t("connections.title")}</h1>
      <p className="mt-1 max-w-2xl text-[15px] text-fg-2">Your connected apps. Official logins only, read-only: we never post for you and never scrape.</p>
      {q.data.sample_data && (
        <p className="mt-3 rounded-2xl border border-warn/40 bg-warn-soft p-3 text-sm">
          Your profile uses sample insights from onboarding (demo). Connect a real account and its numbers are labelled Live data.
        </p>
      )}
      <ul className="mt-6 divide-y divide-line overflow-hidden rounded-[var(--radius-card)] border border-line bg-surface">
        <li>
          <YouTubeRow creatorId={id} status={by.youtube} />
        </li>
        <li>
          <InstagramRow creatorId={id} status={by.instagram} />
        </li>
      </ul>
      <p className="mt-4 text-sm text-muted">
        Questions, or want to remove an app's access?{" "}
        <Link to="/creator/help" className="font-medium text-accent underline-offset-4 hover:underline">
          Go to Help
        </Link>
      </p>
    </div>
  );
}

function Row({ icon, name, status, line, children }: { icon: ReactNode; name: string; status: Status; line: ReactNode; children?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-3 px-4 py-4 sm:px-5">
      <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-surface-2">{icon}</span>
      <div className="min-w-0 flex-1">
        <p className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="font-semibold">{name}</span>
          <StatusChip status={status} />
        </p>
        <p className="mt-0.5 truncate text-[13px] text-muted">{line}</p>
      </div>
      {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
    </div>
  );
}

function useRefreshAll() {
  const qc = useQueryClient();
  // A connection's numbers drive the whole profile: every screen built from it refetches.
  return () => void qc.invalidateQueries();
}

function YouTubeRow({ creatorId, status }: { creatorId: string; status: PlatformStatus }) {
  const qc = useQueryClient();
  const refreshAll = useRefreshAll();
  const [handle, setHandle] = useState("");
  const [linking, setLinking] = useState(false);
  const q = useQuery({ queryKey: ["youtube", creatorId], queryFn: () => api<LinkedYouTube>(`/creators/${creatorId}/youtube`), enabled: status.status !== "unavailable" });
  const done = (d: LinkedYouTube) => {
    qc.setQueryData(["youtube", creatorId], d);
    refreshAll();
  };
  const link = useMutation({
    mutationFn: (h: string) => post<LinkedYouTube>(`/creators/${creatorId}/youtube/link`, { handle: h }),
    onSuccess: (d) => {
      done(d);
      setLinking(false);
      toast.success("YouTube connected", { description: "Your channel's numbers are now on Home." });
    },
    onError: (e) => toast.error((e as Error).message),
  });
  const [busy, setBusy] = useState(false);
  const analytics = async () => {
    setBusy(true);
    try {
      done(await post<LinkedYouTube>("/connect/youtube/analytics", { access_token: await youtubeAnalyticsToken() }));
      toast.success("YouTube Analytics connected");
    } catch (e) {
      const msg = firebaseMessage(e);
      if (msg) toast.error(msg);
    } finally {
      setBusy(false);
    }
  };
  const d = q.data;
  const ch = d?.linked ? d.channel : null;
  const line = ch
    ? [ch.title, ch.handle, `updated ${when(ch.fetched_at) ?? "recently"}`, d?.analytics ? "Analytics on" : null].filter(Boolean).join(" · ")
    : status.status === "unavailable"
      ? status.detail
      : "Sign in with YouTube and it connects automatically, with Analytics.";
  return (
    <>
      <Row icon={<Youtube className="size-5 text-[#ff0033]" aria-hidden />} name="YouTube" status={status.status} line={line}>
        {ch ? (
          <>
            {!d?.analytics && firebaseEnabled && (
              <Button size="sm" variant="ghost" loading={busy} onClick={analytics}>
                Add Analytics
              </Button>
            )}
            <Button size="sm" variant="outline" loading={link.isPending} onClick={() => link.mutate(ch.handle ?? ch.channel_id ?? "")}>
              {!link.isPending && <RefreshCw aria-hidden />} Refresh
            </Button>
          </>
        ) : (
          status.status !== "unavailable" &&
          !linking && (
            <Button size="sm" variant="primary" onClick={() => setLinking(true)}>
              <Link2 aria-hidden /> Connect
            </Button>
          )
        )}
      </Row>
      {linking && !ch && (
        <form
          className="flex flex-wrap items-center gap-2 border-t border-line px-4 py-3 sm:px-5"
          onSubmit={(e) => {
            e.preventDefault();
            link.mutate(handle);
          }}
        >
          <Input value={handle} onChange={(e) => setHandle(e.target.value)} placeholder="@yourchannel or channel link" aria-label="Your channel's @handle or link" className="min-w-[220px] flex-1" required autoFocus />
          <Button type="submit" size="sm" variant="primary" loading={link.isPending}>
            Connect channel
          </Button>
          <Button type="button" size="sm" variant="ghost" onClick={() => setLinking(false)}>
            Cancel
          </Button>
        </form>
      )}
    </>
  );
}

function InstagramRow({ creatorId, status }: { creatorId: string; status: PlatformStatus }) {
  const qc = useQueryClient();
  const refreshAll = useRefreshAll();
  const [params, setParams] = useSearchParams();
  const [consent, setConsent] = useState(false);
  const available = status.status !== "unavailable";
  const q = useQuery({ queryKey: ["instagram", creatorId], queryFn: () => api<InstagramData>(`/creators/${creatorId}/instagram`), enabled: available });

  // Instagram sends the browser back with ?ig=connected or ?ig=error&msg=...
  useEffect(() => {
    const result = params.get("ig");
    if (!result) return;
    const msg = params.get("msg");
    if (result === "connected") toast.success("Instagram connected", { description: msg ?? "Your numbers are now on Home." });
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
  const sync = useMutation({
    mutationFn: () => post<InstagramData>("/connect/instagram/sync"),
    onSuccess: (d) => {
      qc.setQueryData(["instagram", creatorId], d);
      refreshAll();
      toast.success("Instagram synced");
    },
    onError: (e) => toast.error((e as Error).message),
  });
  const acct = q.data?.account;
  const st = q.data?.status ?? status;
  const line =
    acct && st.status !== "not_connected"
      ? [acct.username ? `@${acct.username}` : null, `updated ${when(acct.fetched_at) ?? "recently"}`].filter(Boolean).join(" · ")
      : st.status === "unavailable"
        ? st.detail
        : st.status === "expired" || st.status === "error"
          ? st.detail
          : "Sign in with Instagram and it connects automatically.";
  return (
    <>
      <Row icon={<Instagram className="size-5 text-[#e1306c]" aria-hidden />} name="Instagram" status={st.status} line={line}>
        {acct && st.status === "connected" && (
          <Button size="sm" variant="outline" loading={sync.isPending} onClick={() => sync.mutate()}>
            {!sync.isPending && <RefreshCw aria-hidden />} Sync now
          </Button>
        )}
        {available && (st.status === "not_connected" || st.status === "expired" || st.status === "error") && (
          <Button size="sm" variant="primary" onClick={() => setConsent(true)}>
            <Instagram aria-hidden /> {st.status === "not_connected" ? "Connect" : "Reconnect"}
          </Button>
        )}
      </Row>
      <Dialog open={consent} onOpenChange={setConsent}>
        <DialogContent title="Connect Instagram" description="Official Instagram login. Read-only.">
          <p className="rounded-2xl border border-line bg-surface-2 p-4 text-sm leading-relaxed">{q.data?.consent}</p>
          <p className="mt-3 flex gap-2 text-xs text-muted">
            <ShieldCheck className="size-4 shrink-0 text-success" aria-hidden />
            Your account must be a Creator or Business account. While the DealMeet app is in development mode, only accounts added as Instagram Testers can
            connect.
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
    </>
  );
}
