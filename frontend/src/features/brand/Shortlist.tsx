import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, FilePen, Info, Send, Star, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Avatar, ErrorState } from "@/components/shared/Bits";
import { SourceBadge } from "@/components/shared/SourceBadge";
import { TrustBadge } from "@/components/shared/TrustBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox, Input, Label, Skeleton, Textarea } from "@/components/ui/form";
import { Dialog, DialogContent, Popover, PopoverContent, PopoverTrigger } from "@/components/ui/overlays";
import { api, del, post, put } from "@/lib/api";
import { inr, inrRange, pct } from "@/lib/format";
import type { BrandMatch, Listing, OfferDraft, RankCriterion, Shortlist } from "@/lib/market-types";
import { cn } from "@/lib/utils";

/** How a creator's rank was built: each part, its weight, and any missing data. */
export function RankWhy({ m, criteria }: { m: BrandMatch; criteria?: RankCriterion[] }) {
  if (!m.ranking) return null;
  return (
    <Popover>
      <PopoverTrigger className="inline-flex items-center gap-1 text-xs text-muted underline decoration-dotted underline-offset-4 hover:text-fg">
        <Info className="size-3.5" aria-hidden /> Why ranked here
      </PopoverTrigger>
      <PopoverContent className="w-[22rem] max-w-[calc(100vw-2rem)]">
        <p className="text-sm font-semibold">Rank {(m.rank * 100).toFixed(0)} / 100</p>
        <table className="mt-2 w-full text-left text-xs">
          <thead className="text-muted">
            <tr>
              <th scope="col" className="py-1 font-medium">Part</th>
              <th scope="col" className="py-1 text-right font-medium">Weight</th>
              <th scope="col" className="py-1 text-right font-medium">Score</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {m.ranking.map((r) => (
              <tr key={r.key} className="align-top">
                <th scope="row" className="py-1.5 font-medium" title={criteria?.find((c) => c.key === r.key)?.how}>
                  {r.label}
                  {r.note && <span className="block font-normal text-muted">{r.note}</span>}
                </th>
                <td className="num py-1.5 text-right">{Math.round(r.weight * 100)}%</td>
                <td className="num py-1.5 text-right">{r.score === null ? "Hidden" : r.score.toFixed(2)}{r.missing && " *"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {m.ranking.some((r) => r.missing) && <p className="mt-1 text-[11px] text-muted">* Data missing: scored as neutral, not as a penalty.</p>}
        {m.evidence && m.evidence.length > 0 && (
          <>
            <p className="mt-3 text-xs font-semibold">Shared with you</p>
            <ul className="mt-1 space-y-1">
              {m.evidence.map((e) => (
                <li key={e.key} className="flex flex-wrap items-center gap-1.5 text-xs">
                  <span className="text-fg-2">{e.label}:</span> <span className="num font-medium">{e.value}</span> <SourceBadge source={e.source} />
                </li>
              ))}
            </ul>
          </>
        )}
        {m.limitations && m.limitations.length > 0 && (
          <>
            <p className="mt-3 text-xs font-semibold">Limits of this data</p>
            <ul className="mt-1 list-disc space-y-0.5 pl-4 text-xs text-fg-2">
              {m.limitations.map((l) => (
                <li key={l}>{l}</li>
              ))}
            </ul>
          </>
        )}
      </PopoverContent>
    </Popover>
  );
}

export function useShortlist(listingId: string) {
  return useQuery({ queryKey: ["shortlist", listingId], queryFn: () => api<Shortlist>(`/campaigns/${listingId}/shortlist`) });
}

/** Add to or remove from this campaign's shortlist. */
export function ShortlistToggle({ listingId, creatorId, name, on }: { listingId: string; creatorId: string; name: string; on: boolean }) {
  const qc = useQueryClient();
  const toggle = useMutation({
    mutationFn: () => (on ? del<Shortlist>(`/campaigns/${listingId}/shortlist/${creatorId}`) : put<Shortlist>(`/campaigns/${listingId}/shortlist/${creatorId}`, {})),
    onSuccess: (d) => {
      qc.setQueryData(["shortlist", listingId], d);
      void qc.invalidateQueries({ queryKey: ["matches", listingId] });
      void qc.invalidateQueries({ queryKey: ["applications", listingId] });
    },
    onError: (e) => toast.error((e as Error).message),
  });
  return (
    <Button size="sm" variant={on ? "outline" : "ghost"} loading={toggle.isPending} onClick={() => toggle.mutate()} aria-pressed={on} aria-label={on ? `Remove ${name} from the shortlist` : `Shortlist ${name}`}>
      {!toggle.isPending && <Star aria-hidden className={cn(on && "fill-current text-accent")} />} {on ? "Shortlisted" : "Shortlist"}
    </Button>
  );
}

/** The saved shortlist: notes, picking 2 to 4 to compare, and offer drafts. */
export function ShortlistPanel({
  listing,
  criteria,
  selected,
  onSelect,
  onCompare,
}: {
  listing: Listing;
  criteria?: RankCriterion[];
  selected: string[];
  onSelect: (ids: string[]) => void;
  onCompare: () => void;
}) {
  const qc = useQueryClient();
  const q = useShortlist(listing.id);
  const drafts = useQuery({ queryKey: ["drafts", listing.id], queryFn: () => api<{ items: OfferDraft[] }>(`/campaigns/${listing.id}/offer-drafts`) });
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["shortlist", listing.id] });
    void qc.invalidateQueries({ queryKey: ["drafts", listing.id] });
    void qc.invalidateQueries({ queryKey: ["matches", listing.id] });
  };
  const note = useMutation({
    mutationFn: ({ id, text }: { id: string; text: string }) => put<Shortlist>(`/campaigns/${listing.id}/shortlist/${id}`, { note: text || null }),
    onSuccess: (d) => qc.setQueryData(["shortlist", listing.id], d),
    onError: (e) => toast.error((e as Error).message),
  });
  const remove = useMutation({
    mutationFn: (id: string) => del<Shortlist>(`/campaigns/${listing.id}/shortlist/${id}`),
    onSuccess: (d, id) => {
      qc.setQueryData(["shortlist", listing.id], d);
      onSelect(selected.filter((x) => x !== id));
      refresh();
    },
    onError: (e) => toast.error((e as Error).message),
  });
  const draft = useMutation({
    mutationFn: (id: string) => post<OfferDraft & { created: boolean }>(`/campaigns/${listing.id}/offer-drafts`, { creator_id: id }),
    onSuccess: (d) => {
      refresh();
      toast.success(d.created ? `Draft offer for ${d.creator_name}` : "That draft already exists", { description: "Edit it below. Nothing is sent until you confirm." });
    },
    onError: (e) => toast.error((e as Error).message),
  });

  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data) return <Skeleton className="h-48 rounded-xl" />;
  const items = q.data.items;
  const toggle = (id: string) => onSelect(selected.includes(id) ? selected.filter((x) => x !== id) : selected.length >= 4 ? selected : [...selected, id]);
  const openDrafts = (drafts.data?.items ?? []).filter((d) => d.status !== "sent");

  return (
    <div className="space-y-4">
      {items.length === 0 ? (
        <p className="card-surface rounded-xl p-5 text-sm text-fg-2">Nothing shortlisted yet. Use Shortlist on a match to save them here with a note.</p>
      ) : (
        <>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm text-fg-2">
              {items.length} shortlisted · pick 2 to 4 to compare ({selected.length} picked)
            </p>
            <Button size="sm" variant="outline" disabled={selected.length < 2} onClick={onCompare}>
              Compare {selected.length >= 2 ? selected.length : ""}
            </Button>
          </div>
          <ul className="card-surface divide-y divide-line rounded-xl">
            {items.map((m) =>
              m.available ? (
                <li key={m.id} className="grid gap-3 px-4 py-3.5 md:grid-cols-[auto_minmax(0,2fr)_minmax(0,1.6fr)_auto] md:items-start">
                  <Checkbox checked={selected.includes(m.id)} onCheckedChange={() => toggle(m.id)} disabled={!selected.includes(m.id) && selected.length >= 4} aria-label={`Compare ${m.name}`} className="mt-2" />
                  <div className="flex min-w-0 gap-3">
                    <Avatar name={m.name} hue={m.avatar_hue} size={36} generic={m.is_reference} />
                    <div className="min-w-0">
                      <p className="flex flex-wrap items-center gap-1.5 text-sm font-medium">
                        <Link to={`/brand/creators/${m.id}?listing=${listing.id}`} className="hover:text-accent">
                          {m.name}
                        </Link>
                        <TrustBadge trust={m.trust} />
                        {m.deal_stage && <Badge size="sm" variant="success">{m.deal_stage === "offer" ? "Offer sent" : "In a deal"}</Badge>}
                      </p>
                      <p className="truncate text-xs text-muted">
                        {m.niche_label} · {m.languages.join(", ")} · fit {m.fit}
                      </p>
                      <RankWhy m={m} criteria={criteria} />
                    </div>
                  </div>
                  <NoteField initial={m.note ?? ""} name={m.name} onSave={(text) => note.mutate({ id: m.id, text })} />
                  <div className="flex flex-wrap items-center gap-1.5 md:justify-end">
                    <span className="num text-xs text-fg-2">
                      Est. {inrRange(m.fair.range.low, m.fair.range.high)}
                    </span>
                    {!m.deal_stage && !m.draft && (
                      <Button size="sm" variant="outline" loading={draft.isPending && draft.variables === m.id} onClick={() => draft.mutate(m.id)}>
                        <FilePen aria-hidden /> Draft offer
                      </Button>
                    )}
                    <Button size="sm" variant="ghost" onClick={() => remove.mutate(m.id)} aria-label={`Remove ${m.name} from the shortlist`}>
                      <Trash2 aria-hidden />
                    </Button>
                  </div>
                </li>
              ) : (
                <li key={m.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-sm">
                  <span className="text-fg-2">
                    A creator who stopped sharing with you{m.note ? ` · your note: “${m.note}”` : ""}
                  </span>
                  <Button size="sm" variant="ghost" onClick={() => remove.mutate(m.id)}>
                    <Trash2 aria-hidden /> Remove
                  </Button>
                </li>
              ),
            )}
          </ul>
        </>
      )}

      {openDrafts.length > 0 && (
        <section aria-labelledby="drafts">
          <h3 id="drafts" className="mb-2 text-sm font-semibold">
            Draft offers
          </h3>
          <ul className="grid gap-3 lg:grid-cols-2">
            {openDrafts.map((d) => (
              <DraftCard key={d.id} draft={d} listing={listing} onChange={refresh} />
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function NoteField({ initial, name, onSave }: { initial: string; name: string; onSave: (text: string) => void }) {
  const [text, setText] = useState(initial);
  return (
    <Input
      value={text}
      onChange={(e) => setText(e.target.value)}
      onBlur={() => text !== initial && onSave(text)}
      onKeyDown={(e) => e.key === "Enter" && (e.currentTarget as HTMLInputElement).blur()}
      placeholder="Add a note"
      maxLength={280}
      aria-label={`Note about ${name}`}
      className="h-9 text-sm"
    />
  );
}

function DraftCard({ draft, listing, onChange }: { draft: OfferDraft; listing: Listing; onChange: () => void }) {
  const [amount, setAmount] = useState(String(draft.amount));
  const [message, setMessage] = useState(draft.message ?? "");
  const [confirm, setConfirm] = useState(false);
  const n = Number(amount.replace(/[^\d]/g, "")) || 0;
  const fair = draft.fair_estimate?.total ?? 0;
  const below = fair ? 1 - n / fair : 0;
  const dirty = n !== draft.amount || (message || null) !== draft.message;
  const save = useMutation({
    mutationFn: () => api<OfferDraft>(`/offer-drafts/${draft.id}`, { method: "PATCH", json: { amount: n, message: message || null } }),
    onSuccess: () => {
      onChange();
      toast.success("Draft saved");
    },
    onError: (e) => toast.error((e as Error).message),
  });
  const send = useMutation({
    mutationFn: async () => {
      if (dirty) await api(`/offer-drafts/${draft.id}`, { method: "PATCH", json: { amount: n, message: message || null } });
      return post<OfferDraft & { duplicate: boolean }>(`/offer-drafts/${draft.id}/send`, { confirm: true });
    },
    onSuccess: () => {
      setConfirm(false);
      onChange();
      toast.success(`Offer sent to ${draft.creator_name}`, { description: `${inr(n)} for ${listing.title}. Once they accept, sign and fund escrow before they post.` });
    },
    onError: (e) => {
      setConfirm(false);
      toast.error((e as Error).message);
    },
  });
  return (
    <li className="card-surface rounded-xl p-4">
      <p className="flex items-center gap-2 text-sm font-medium">
        <Avatar name={draft.creator_name ?? "?"} hue={draft.avatar_hue} size={26} generic={draft.is_reference} /> {draft.creator_name}
        <Badge size="sm" variant="outline">Draft · not sent</Badge>
      </p>
      <div className="mt-3 grid gap-3 sm:grid-cols-[10rem_1fr]">
        <div>
          <Label htmlFor={`amt-${draft.id}`}>Offer (₹)</Label>
          <Input id={`amt-${draft.id}`} inputMode="numeric" value={amount} onChange={(e) => setAmount(e.target.value)} className="h-9 text-sm" />
        </div>
        <div>
          <Label htmlFor={`msg-${draft.id}`}>Message</Label>
          <Textarea id={`msg-${draft.id}`} value={message} onChange={(e) => setMessage(e.target.value)} maxLength={400} className="min-h-9 py-2 text-sm" />
        </div>
      </div>
      {draft.fair_estimate && (
        <p className="mt-2 text-xs text-muted">
          Estimated fair price {inrRange(draft.fair_estimate.range.low, draft.fair_estimate.range.high)} for this campaign's deliverables. An estimate, not a quote.
        </p>
      )}
      {below >= 0.3 && (
        <p className="mt-1 flex items-start gap-1.5 text-xs text-warn">
          <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden /> {Math.round(below * 100)}% below the estimate. Low offers are usually countered.
        </p>
      )}
      <div className="mt-3 flex flex-wrap justify-end gap-2">
        <Button size="sm" variant="ghost" disabled={!dirty || n < 500} loading={save.isPending} onClick={() => save.mutate()}>
          Save draft
        </Button>
        <Button size="sm" variant="primary" disabled={n < 500} onClick={() => setConfirm(true)}>
          <Send aria-hidden /> Review and send
        </Button>
      </div>
      <Dialog open={confirm} onOpenChange={setConfirm}>
        <DialogContent title={`Send ${inr(n)} to ${draft.creator_name}?`} description={`For ${listing.title}. They'll see the offer in their deals and can accept, counter or decline.`}>
          {message && <p className="rounded-xl bg-surface-2 p-3 text-sm text-fg-2">“{message}”</p>}
          <div className="mt-4 flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setConfirm(false)}>
              Not yet
            </Button>
            <Button variant="primary" loading={send.isPending} onClick={() => send.mutate()}>
              {!send.isPending && <Send aria-hidden />} Confirm and send
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </li>
  );
}

/** 2 to 4 shortlisted creators side by side. Opening this is logged in each creator's ledger. */
export function ComparePanel({ listing, ids }: { listing: Listing; ids: string[] }) {
  const q = useQuery({
    queryKey: ["compare", listing.id, ids],
    queryFn: () => api<{ items: (BrandMatch & { note: string | null })[]; criteria: RankCriterion[] }>(`/campaigns/${listing.id}/compare?ids=${ids.join(",")}`),
    enabled: ids.length >= 2,
  });
  if (ids.length < 2) return <p className="text-sm text-muted">Pick two to four creators on the Shortlist tab to compare them here.</p>;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data) return <Skeleton className="h-64 rounded-xl" />;
  const items = q.data.items;
  const ev = (m: BrandMatch, key: string) => m.evidence?.find((e) => e.key === key);
  const shared = (m: BrandMatch, key: string) => {
    const e = ev(m, key);
    return e ? (
      <span className="flex flex-wrap items-center gap-1.5">
        <span className="num">{e.value}</span> <SourceBadge source={e.source} />
      </span>
    ) : (
      <span className="text-xs text-muted">Not shared</span>
    );
  };
  const rows: { label: string; get: (m: BrandMatch & { note: string | null }) => React.ReactNode }[] = [
    { label: "Rank", get: (m) => <span className="num font-semibold">{(m.rank * 100).toFixed(0)} / 100</span> },
    { label: "Fit", get: (m) => <span className="num">{m.fit}</span> },
    { label: "Estimated price", get: (m) => <span className="num font-semibold">{inrRange(m.fair.range.low, m.fair.range.high)}</span> },
    { label: "Followers", get: (m) => shared(m, "followers") },
    { label: "Median views", get: (m) => shared(m, "median_views") },
    { label: "Saves + shares per view", get: (m) => (m.engagement !== null ? <span className="num">{pct(m.engagement, 1)}</span> : <span className="text-xs text-muted">Not shared</span>) },
    { label: "Largest age group", get: (m) => shared(m, "age") },
    { label: "Trust", get: (m) => <TrustBadge trust={m.trust} /> },
    { label: "Audience size", get: (m) => m.audience_stage },
    { label: "Languages", get: (m) => m.languages.join(", ") },
    { label: "Why they fit", get: (m) => <ul className="space-y-1 text-xs text-fg-2">{m.reasons.map((r) => <li key={r}>{r}</li>)}</ul> },
    { label: "Limits", get: (m) => <ul className="list-disc space-y-0.5 pl-4 text-xs text-fg-2">{m.limitations?.map((r) => <li key={r}>{r}</li>)}</ul> },
    { label: "Your note", get: (m) => <span className="text-xs text-fg-2">{m.note || "—"}</span> },
  ];
  return (
    <div className="card-surface overflow-x-auto rounded-xl">
      <table className="w-full min-w-[640px] text-left text-[13px]">
        <thead>
          <tr className="border-b border-line">
            <th scope="col" className="w-40 px-4 py-3 text-xs font-medium text-muted">
              <span className="sr-only">Attribute</span>
            </th>
            {items.map((m) => (
              <th key={m.id} scope="col" className="px-4 py-3">
                <span className="flex items-center gap-2">
                  <Avatar name={m.name} hue={m.avatar_hue} size={28} generic={m.is_reference} />
                  <span className="font-semibold">{m.name}</span>
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {rows.map((r) => (
            <tr key={r.label}>
              <th scope="row" className="px-4 py-2.5 text-xs font-medium text-muted">
                {r.label}
              </th>
              {items.map((m) => (
                <td key={m.id} className="px-4 py-2.5 align-top">
                  {r.get(m)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="border-t border-line px-4 py-2 text-[11px] text-muted">
        Prices are estimates. Opening this view is recorded in each creator's consent ledger.
      </p>
    </div>
  );
}
