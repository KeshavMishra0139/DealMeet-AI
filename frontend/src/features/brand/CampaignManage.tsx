import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, Check, CircleDot, Lock, Pause, Pencil, Play, Star, X } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Avatar, ErrorState } from "@/components/shared/Bits";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/overlays";
import { api, ApiError, post, type MissingItem } from "@/lib/api";
import { shortDate, timeOfDay } from "@/lib/format";
import type { CampaignAction, CampaignApplications, Listing } from "@/lib/market-types";
import { useBrandId } from "@/lib/session";
import { cn } from "@/lib/utils";
import { CampaignStatusBadge } from "./CampaignStatus";
import { useLoadWipe, DetailSkeleton } from "@/components/shared/Skeletons";

const ACTION: Record<CampaignAction, { label: string; Icon: typeof Play; done: string }> = {
  publish: { label: "Publish", Icon: CircleDot, done: "Campaign live: matching creators can see it and apply." },
  pause: { label: "Pause", Icon: Pause, done: "Paused: no new applications or offers until you resume." },
  resume: { label: "Resume", Icon: Play, done: "Live again." },
  close: { label: "Close", Icon: Lock, done: "Closed. This is final." },
};

/** Status, the actions open now, and what's missing before it can go live. */
export function CampaignControls({ listing }: { listing: Listing }) {
  const qc = useQueryClient();
  const brandId = useBrandId();
  const [problems, setProblems] = useState<MissingItem[]>([]);
  const [confirmClose, setConfirmClose] = useState(false);
  const act = useMutation({
    mutationFn: (action: CampaignAction) => post<Listing & { changed: boolean }>(`/campaigns/${listing.id}/status`, { action }),
    onSuccess: (l, action) => {
      setProblems([]);
      qc.setQueryData(["listing", listing.id], l);
      void qc.invalidateQueries({ queryKey: ["console", brandId] });
      if (l.changed) toast.success(ACTION[action].done);
    },
    onError: (e) => {
      setProblems(e instanceof ApiError ? e.missing : []);
      toast.error((e as Error).message);
    },
  });
  const actions = listing.actions ?? [];
  const missing = problems.length ? problems : listing.status === "draft" ? (listing.missing ?? []) : [];

  return (
    <div className="mt-3">
      <div className="flex flex-wrap items-center gap-2">
        <CampaignStatusBadge status={listing.status} />
        {listing.status !== "closed" && (
          <Button asChild size="sm" variant="ghost">
            <Link to={`/brand/campaigns/${listing.id}/edit`}>
              <Pencil aria-hidden /> Edit
            </Link>
          </Button>
        )}
        {actions
          .filter((a) => a !== "close")
          .map((a) => {
            const { label, Icon } = ACTION[a];
            return (
              <Button key={a} size="sm" variant={a === "publish" || a === "resume" ? "primary" : "outline"} loading={act.isPending && act.variables === a} onClick={() => act.mutate(a)}>
                {!(act.isPending && act.variables === a) && <Icon aria-hidden />} {label}
              </Button>
            );
          })}
        {actions.includes("close") && (
          <Button size="sm" variant="ghost" onClick={() => setConfirmClose(true)}>
            <Lock aria-hidden /> Close
          </Button>
        )}
      </div>
      {listing.status === "draft" && <p className="mt-2 text-xs text-muted">Drafts are hidden from creators. Nobody can apply or be offered this campaign until it's live.</p>}
      {listing.status === "paused" && <p className="mt-2 text-xs text-muted">Paused: creators who applied can still see it; nobody new can apply, and offers wait until you resume.</p>}
      {listing.status === "closed" && <p className="mt-2 text-xs text-muted">Closed campaigns can't be reopened or edited. Deals already made carry on.</p>}
      {missing.length > 0 && (
        <div role="status" className="mt-3 max-w-xl rounded-xl border border-warn/40 bg-warn-soft p-3 text-sm">
          <p className="flex items-center gap-1.5 font-medium">
            <AlertCircle className="size-4 text-warn" aria-hidden /> Before it can go live
          </p>
          <ul className="mt-1 list-disc space-y-0.5 pl-5 text-[13px] text-fg-2">
            {missing.map((m) => (
              <li key={m.field + m.message}>{m.message}</li>
            ))}
          </ul>
        </div>
      )}
      <Dialog open={confirmClose} onOpenChange={setConfirmClose}>
        <DialogContent title="Close this campaign?" description="Closing is final: it can't be reopened or edited. Deals already made carry on.">
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setConfirmClose(false)}>
              Keep it
            </Button>
            <Button
              variant="primary"
              loading={act.isPending}
              onClick={() => {
                act.mutate("close");
                setConfirmClose(false);
              }}
            >
              Close campaign
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

const GROUPS = [
  { key: "applied", label: "Applied" },
  { key: "shortlisted", label: "Shortlisted" },
  { key: "offered", label: "Offered" },
  { key: "declined", label: "Declined" },
] as const;

export function useApplications(listingId: string) {
  return useQuery({ queryKey: ["applications", listingId], queryFn: () => api<CampaignApplications>(`/campaigns/${listingId}/applications`) });
}

/** Applications to this campaign, by state. Shortlist or decline; an offer moves one to Offered. */
export function ApplicationsPanel({ listing }: { listing: Listing }) {
  const qc = useQueryClient();
  const q = useApplications(listing.id);
  const set = useMutation({
    mutationFn: ({ creatorId, status }: { creatorId: string; status: "applied" | "shortlisted" | "declined" }) =>
      post<CampaignApplications>(`/campaigns/${listing.id}/applications/${creatorId}`, { status }),
    onSuccess: (d) => qc.setQueryData(["applications", listing.id], d),
    onError: (e) => toast.error((e as Error).message),
  });
  const ready = useLoadWipe(!!q.data);
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data || !ready) return <DetailSkeleton label="Loading campaign" />;
  const d = q.data;
  if (d.items.length === 0)
    return (
      <p className="card-surface rounded-xl p-5 text-sm text-fg-2">
        {listing.status === "live" ? "No applications yet. Creators who fit see this campaign in their opportunities." : `No applications. ${listing.status === "draft" ? "Publish the campaign so creators can apply." : ""}`}
      </p>
    );
  const closed = listing.status === "closed";
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {GROUPS.map((g) => {
        const items = d.items.filter((i) => i.status === g.key);
        return (
          <section key={g.key} aria-labelledby={`apps-${g.key}`} className="card-surface rounded-xl p-4">
            <h3 id={`apps-${g.key}`} className="flex items-center justify-between text-sm font-semibold">
              {g.label} <span className="num rounded-full bg-surface-2 px-2 text-xs font-medium text-fg-2">{d.counts[g.key]}</span>
            </h3>
            {items.length === 0 ? (
              <p className="mt-2 text-xs text-muted">None.</p>
            ) : (
              <ul className="mt-2 divide-y divide-line">
                {items.map((i) => (
                  <li key={i.creator_id} className="flex flex-wrap items-center gap-2.5 py-2.5">
                    <Avatar name={i.name} hue={i.avatar_hue} size={32} generic={i.is_reference} />
                    <div className="min-w-0 flex-1">
                      <Link to={`/brand/creators/${i.creator_id}?listing=${listing.id}`} className="text-sm font-medium hover:text-accent">
                        {i.name}
                      </Link>
                      <p className="truncate text-xs text-muted">
                        {i.niche}
                        {i.at && ` · ${shortDate(i.at)}`}
                        {i.message && ` · “${i.message}”`}
                      </p>
                    </div>
                    {!closed && (g.key === "applied" || g.key === "declined") && (
                      <Button size="sm" variant="outline" onClick={() => set.mutate({ creatorId: i.creator_id, status: "shortlisted" })} aria-label={`Shortlist ${i.name}`}>
                        <Star aria-hidden /> Shortlist
                      </Button>
                    )}
                    {!closed && (g.key === "applied" || g.key === "shortlisted") && (
                      <Button size="sm" variant="ghost" onClick={() => set.mutate({ creatorId: i.creator_id, status: "declined" })} aria-label={`Decline ${i.name}`}>
                        <X aria-hidden /> Decline
                      </Button>
                    )}
                    {g.key === "offered" && i.deal_id && (
                      <Button asChild size="sm" variant="ghost">
                        <Link to={`/brand/deals/${i.deal_id}`}>
                          <Check aria-hidden /> Deal
                        </Link>
                      </Button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>
        );
      })}
      {d.counts.withdrawn > 0 && <p className="text-xs text-muted lg:col-span-2">{d.counts.withdrawn} creator{d.counts.withdrawn === 1 ? "" : "s"} withdrew.</p>}
    </div>
  );
}

const HISTORY: Record<string, string> = {
  created: "Created as a draft",
  edited: "Edited",
  publish: "Published",
  pause: "Paused",
  resume: "Resumed",
  close: "Closed",
  application: "Application updated",
};

/** Every change to the campaign, newest first. */
export function HistoryPanel({ listing }: { listing: Listing }) {
  const items = [...(listing.history ?? [])].reverse();
  if (!items.length) return <p className="text-sm text-muted">No changes recorded yet.</p>;
  return (
    <ol className="card-surface divide-y divide-line rounded-xl">
      {items.map((h, i) => (
        <li key={h.at + i} className={cn("flex flex-wrap items-baseline justify-between gap-2 px-4 py-2.5 text-sm")}>
          <span>
            <span className="font-medium">{HISTORY[h.action] ?? h.action}</span>
            {h.fields && <span className="text-fg-2"> · {h.fields.join(", ").replaceAll("_", " ")}</span>}
            {h.action === "application" && h.to && <span className="text-fg-2"> · {h.from} → {h.to}</span>}
          </span>
          <Badge size="sm" variant="outline">
            {shortDate(h.at)}, {timeOfDay(h.at)}
          </Badge>
        </li>
      ))}
    </ol>
  );
}
