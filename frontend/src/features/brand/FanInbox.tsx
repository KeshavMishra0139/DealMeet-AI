import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Heart, Inbox, X } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Avatar, ErrorState } from "@/components/shared/Bits";
import { ReportButton } from "@/components/shared/ReportButton";
import { SourceBadge } from "@/components/shared/SourceBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Label, Skeleton, Switch, Textarea } from "@/components/ui/form";
import { Dialog, DialogContent } from "@/components/ui/overlays";
import { api, post } from "@/lib/api";
import { inr, inrRange, shortDate } from "@/lib/format";
import { useBrandId } from "@/lib/session";
import type { FanProof } from "@/features/creator/Pitches";

interface InboxItem {
  id: string;
  subject: string;
  pitch: string;
  content_ideas: string[];
  lang: "en" | "hi";
  status: "sent" | "accepted" | "declined";
  sent_at: string;
  deal_id: string | null;
  suggested_price_range: { range: { low: number; high: number }; deliverables: string; data_label: string; data_source: string } | null;
  facts: { key: string; label: string; value: string; source: string }[];
  creator: { id: string; name: string; handle: string; avatar_hue: number; is_reference: boolean; niche: string };
  fit: number | null;
  fan_proof: FanProof | null;
  connected: boolean;
}

/** Pitches creators sent this brand, best fit and strongest Fan Proof first. */
export default function FanInbox() {
  const id = useBrandId();
  const [connectedOnly, setConnectedOnly] = useState(false);
  const q = useQuery({
    queryKey: ["fan-inbox", id, connectedOnly],
    queryFn: () => api<{ items: InboxItem[]; open: number }>(`/brands/${id}/fan-inbox?connected_only=${connectedOnly}`),
    enabled: !!id,
  });
  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-semibold tracking-tight">Fan Inbox</h1>
          <p className="mt-1 text-sm text-fg-2">Creators who pitched you, sorted by audience fit and Fan Proof. Accepting sends them an offer in your deals.</p>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <Switch checked={connectedOnly} onCheckedChange={setConnectedOnly} aria-label="Connected accounts only" /> Connected accounts only
        </label>
      </div>
      {q.isError && <ErrorState error={q.error} onRetry={() => q.refetch()} />}
      {!q.data && !q.isError && <Skeleton className="mt-5 h-64 rounded-xl" />}
      {q.data && q.data.items.length === 0 && (
        <p className="card-surface mt-5 rounded-xl p-6 text-center text-sm text-fg-2">
          <Inbox className="mx-auto mb-2 size-6 text-muted" aria-hidden />
          {connectedOnly ? "No pitches from creators with connected accounts yet." : "No pitches yet. Creators can pitch you from your brand page."}
        </p>
      )}
      <ul className="mt-5 space-y-3">
        {q.data?.items.map((p) => (
          <PitchCard key={p.id} p={p} />
        ))}
      </ul>
    </div>
  );
}

function PitchCard({ p }: { p: InboxItem }) {
  const qc = useQueryClient();
  const [accepting, setAccepting] = useState(false);
  const [declining, setDeclining] = useState(false);
  const mid = p.suggested_price_range ? Math.round((p.suggested_price_range.range.low + p.suggested_price_range.range.high) / 2) : 5000;
  const [amount, setAmount] = useState(String(mid));
  const [note, setNote] = useState("");
  const done = () => void qc.invalidateQueries({ queryKey: ["fan-inbox"] });
  const accept = useMutation({
    mutationFn: () => post<{ deal_id: string }>(`/fan-inbox/${p.id}/accept`, { amount: Number(amount.replace(/[^\d]/g, "")) || null }),
    onSuccess: () => {
      setAccepting(false);
      done();
      void qc.invalidateQueries({ queryKey: ["console"] });
      toast.success(`Offer sent to ${p.creator.name}`, { description: "Find it in Deals. Once they accept, sign and fund escrow before they post." });
    },
    onError: (e) => toast.error((e as Error).message),
  });
  const decline = useMutation({
    mutationFn: () => post(`/fan-inbox/${p.id}/decline`, { note: note || null }),
    onSuccess: () => {
      setDeclining(false);
      done();
      toast.success("Declined politely", { description: `${p.creator.name} gets a kind note.` });
    },
    onError: (e) => toast.error((e as Error).message),
  });
  return (
    <li className="card-surface rounded-xl p-4 sm:p-5">
      <div className="flex flex-wrap items-start gap-3">
        <Avatar name={p.creator.name} hue={p.creator.avatar_hue} size={40} generic={p.creator.is_reference} />
        <div className="min-w-0 flex-1">
          <p className="flex flex-wrap items-center gap-2 text-sm font-medium">
            <Link to={`/brand/creators/${p.creator.id}`} className="hover:text-accent">
              {p.creator.name}
            </Link>
            <span className="text-xs font-normal text-muted">
              @{p.creator.handle} · {p.creator.niche}
            </span>
            {p.fit !== null && <Badge size="sm">Fit {p.fit}</Badge>}
            {p.connected ? <Badge size="sm" variant="success">Connected account</Badge> : <Badge size="sm" variant="outline">No connected account</Badge>}
            {p.status !== "sent" && <Badge size="sm" variant={p.status === "accepted" ? "success" : "neutral"}>{p.status === "accepted" ? "Accepted" : "Declined"}</Badge>}
          </p>
          {p.fan_proof && (
            <p className="mt-1 flex items-center gap-1.5 text-xs text-fg-2">
              <Heart className="size-3.5 text-accent" aria-hidden /> {p.fan_proof.label}
            </p>
          )}
          <p className="mt-3 font-medium">{p.subject}</p>
          <p className="mt-1 whitespace-pre-line text-[15px] leading-relaxed text-fg-2" lang={p.lang}>
            {p.pitch}
          </p>
          <ul className="mt-2 list-disc space-y-0.5 pl-5 text-sm text-fg-2" lang={p.lang}>
            {p.content_ideas.map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {p.facts
              .filter((f) => !["niche", "languages"].includes(f.key))
              .map((f) => (
                <span key={f.key} className="inline-flex items-center gap-1.5 rounded-full border border-line px-2.5 py-0.5 text-xs">
                  {f.label}: <span className="num font-medium">{f.value}</span> <SourceBadge source={f.source} />
                </span>
              ))}
          </div>
          <p className="mt-2 text-xs text-muted">
            Sent {shortDate(p.sent_at)}
            {p.suggested_price_range && ` · their estimated rate ${inrRange(p.suggested_price_range.range.low, p.suggested_price_range.range.high)} for ${p.suggested_price_range.deliverables} (an estimate)`}
          </p>
          <ReportButton type="pitch" id={p.id} role="brand" className="-ml-2 mt-1" />
        </div>
        {p.status === "sent" && (
          <div className="flex gap-2">
            <Button size="sm" variant="primary" onClick={() => setAccepting(true)}>
              <Check aria-hidden /> Accept
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setDeclining(true)}>
              <X aria-hidden /> Decline
            </Button>
          </div>
        )}
        {p.status === "accepted" && p.deal_id && (
          <Button asChild size="sm" variant="outline">
            <Link to={`/brand/deals/${p.deal_id}`}>Open the deal</Link>
          </Button>
        )}
      </div>
      <Dialog open={accepting} onOpenChange={setAccepting}>
        <DialogContent title={`Make ${p.creator.name} an offer`} description="It goes into the usual deal flow: they accept or counter, then you sign and fund escrow.">
          <Label htmlFor={`acc-${p.id}`}>Your offer (₹)</Label>
          <Input id={`acc-${p.id}`} inputMode="numeric" value={amount} onChange={(e) => setAmount(e.target.value)} />
          <p className="mt-2 text-xs text-muted">Starts at the middle of their estimated range ({inr(mid)}).</p>
          <div className="mt-4 flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setAccepting(false)}>
              Cancel
            </Button>
            <Button variant="primary" loading={accept.isPending} onClick={() => accept.mutate()}>
              Send offer
            </Button>
          </div>
        </DialogContent>
      </Dialog>
      <Dialog open={declining} onOpenChange={setDeclining}>
        <DialogContent title={`Decline ${p.creator.name}'s pitch?`} description="They get a polite note thanking them. Your own note below stays private.">
          <Label htmlFor={`dec-${p.id}`}>Private note (optional)</Label>
          <Textarea id={`dec-${p.id}`} value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} />
          <div className="mt-4 flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setDeclining(false)}>
              Keep it
            </Button>
            <Button variant="primary" loading={decline.isPending} onClick={() => decline.mutate()}>
              Decline politely
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </li>
  );
}
