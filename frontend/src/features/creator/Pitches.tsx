import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, Link2, Mail, PenLine, Search, Send, Sparkles, Trash2, X } from "lucide-react";
import { useDeferredValue, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { useLoadWipe, ListSkeleton } from "@/components/shared/Skeletons";
import { ErrorState } from "@/components/shared/Bits";
import { SourceBadge } from "@/components/shared/SourceBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { FieldHint, Input, Label, Select, Textarea } from "@/components/ui/form";
import { Dialog, DialogContent } from "@/components/ui/overlays";
import { api, del, post } from "@/lib/api";
import { inrRange, shortDate } from "@/lib/format";
import { htmlLang, isWriteLang, langLabel, WRITE_LANGS, type WriteLang } from "@/lib/languages";
import { useCreatorId } from "@/lib/session";
import { useCreator } from "./CreatorShell";
import type { BrandCard } from "@/features/public/Brands";

export interface FanProof {
  count: number;
  since: string | null;
  label: string;
  platforms: string[];
  links: string[];
}

interface Pitch {
  id: string;
  brand_id: string;
  brand_name: string;
  brand_slug: string | null;
  subject: string;
  pitch: string;
  content_ideas: string[];
  lang: WriteLang;
  /** The language asked for, when the pitch came back in another (no AI: English). */
  lang_requested?: WriteLang | null;
  status: "draft" | "sent" | "shared" | "accepted" | "declined";
  written_by: "ai" | "template";
  suggested_price_range: { range: { low: number; high: number }; deliverables: string; data_label: string; data_source: string } | null;
  fan_proof: FanProof | null;
  facts: { key: string; label: string; value: string; source: string }[];
  created_at: string;
  sent_at: string | null;
  deal_id: string | null;
  on_platform: boolean;
  share: { slug: string; revoked: boolean } | null;
}

interface PitchList {
  items: Pitch[];
  sent_this_week: number;
  per_week: number;
  notifications: { id: string; text: string; at: string }[];
}

const STATUS: Record<Pitch["status"], { label: string; variant: "outline" | "accent" | "success" | "neutral" }> = {
  draft: { label: "Draft", variant: "outline" },
  sent: { label: "In their inbox", variant: "accent" },
  shared: { label: "Share link", variant: "accent" },
  accepted: { label: "Accepted: offer in Deals", variant: "success" },
  declined: { label: "Not this time", variant: "neutral" },
};

/** Pitch brands with your own numbers. You edit before anything is sent. */
export default function Pitches() {
  const id = useCreatorId();
  const qc = useQueryClient();
  const [params] = useSearchParams();
  const list = useQuery({ queryKey: ["pitches", id], queryFn: () => api<PitchList>(`/creators/${id}/pitches`), enabled: !!id });
  const [open, setOpen] = useState<string | null>(null);
  const refresh = () => void qc.invalidateQueries({ queryKey: ["pitches", id] });

  const ready = useLoadWipe(!!list.data);
  if (list.isError) return <ErrorState error={list.error} onRetry={() => list.refetch()} />;
  if (!list.data || !ready) return <ListSkeleton label="Loading your pitches" action />;
  const d = list.data;
  const current = d.items.find((p) => p.id === open);

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-[28px] font-semibold tracking-tight sm:text-[34px]">Pitches</h1>
          <p className="mt-1 text-[15px] text-fg-2">Pitch a brand with your own numbers and Fan Proof. Nothing is sent until you send it.</p>
        </div>
        <Badge variant={d.sent_this_week >= d.per_week ? "warn" : "neutral"}>
          {d.sent_this_week} of {d.per_week} sent this week
        </Badge>
      </div>

      <NewPitch creatorId={id} initialBrand={params.get("brand")} initialName={params.get("name")} onCreated={(pid) => (refresh(), setOpen(pid))} />

      {current && current.status === "draft" && <Editor key={current.id} creatorId={id} pitch={current} onDone={() => (refresh(), setOpen(null))} />}

      {d.notifications.length > 0 && (
        <ul className="mt-6 space-y-2">
          {d.notifications.map((n) => (
            <li key={n.id} className="card-surface rounded-xl px-4 py-3 text-sm text-fg-2">
              <Mail className="mr-1.5 inline size-4 text-muted" aria-hidden /> {n.text} <span className="text-xs text-muted">· {shortDate(n.at)}</span>
            </li>
          ))}
        </ul>
      )}

      <section aria-labelledby="mine" className="mt-8">
        <h2 id="mine" className="mb-3 font-display text-lg font-semibold">
          Your pitches
        </h2>
        {d.items.length === 0 ? (
          <p className="card-surface rounded-xl p-5 text-sm text-fg-2">No pitches yet. Pick a brand above to write your first one.</p>
        ) : (
          <ul className="card-surface divide-y divide-line rounded-xl">
            {d.items.map((p) => (
              <PitchRow key={p.id} p={p} creatorId={id} onEdit={() => setOpen(p.id)} onChange={refresh} />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function NewPitch({
  creatorId,
  initialBrand,
  initialName,
  onCreated,
}: {
  creatorId: string;
  initialBrand: string | null;
  initialName: string | null;
  onCreated: (id: string) => void;
}) {
  const [q, setQ] = useState("");
  const [brand, setBrand] = useState<BrandCard | null>(null);
  const creator = useCreator().data;
  const [picked, setLang] = useState<WriteLang | null>(null);
  const lang: WriteLang = picked ?? (creator?.languages.find(isWriteLang) || "en");
  const query = useDeferredValue(q);
  const dream = useQuery({ queryKey: ["dream", creatorId], queryFn: () => api<{ items: BrandCard[] }>(`/creators/${creatorId}/dream-brands`), enabled: !!creatorId });
  const found = useQuery({
    queryKey: ["directory", "pitch", query],
    queryFn: () => api<{ items: BrandCard[] }>(`/directory/brands?q=${encodeURIComponent(query)}`, { role: null }),
    enabled: query.trim().length >= 2,
    placeholderData: keepPreviousData,
  });
  useEffect(() => {
    if (initialBrand && !brand) {
      const hit = dream.data?.items.find((b) => b.id === initialBrand);
      if (hit) setBrand(hit);
    }
  }, [initialBrand, brand, dream.data]);
  const write = useMutation({
    mutationFn: () => post<Pitch>(`/creators/${creatorId}/pitches`, { brand_id: brand?.id ?? initialBrand, lang }),
    onSuccess: (p) => {
      if (p.lang_requested && p.lang !== p.lang_requested) {
        toast.info(`Written in ${langLabel(p.lang)}`, { description: `AI writing isn't available right now, so this pitch is in ${langLabel(p.lang)} instead of ${langLabel(p.lang_requested)}.` });
      }
      onCreated(p.id);
    },
    onError: (e) => toast.error((e as Error).message),
  });
  const options = query.trim().length >= 2 ? (found.data?.items ?? []) : (dream.data?.items ?? []);
  const chosen = brand ?? (initialBrand ? { id: initialBrand, name: initialName ?? "the brand you picked" } : null);

  return (
    <section aria-labelledby="new" className="card-surface mt-6 rounded-[var(--radius-card)] p-5">
      <h2 id="new" className="flex items-center gap-1.5 font-display text-lg font-semibold">
        <Sparkles className="size-4 text-accent" aria-hidden /> New pitch
      </h2>
      <div className="mt-3 grid gap-4 sm:grid-cols-[1fr_auto]">
        <div>
          <Label htmlFor="np-brand">Brand</Label>
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" aria-hidden />
            <Input id="np-brand" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search brands, or pick a Dream Brand below" className="pl-9" maxLength={80} />
          </div>
          <ul className="mt-2 flex flex-wrap gap-1.5" aria-label={query.trim().length >= 2 ? "Search results" : "Your Dream Brands"}>
            {options.slice(0, 8).map((b) => (
              <li key={b.id}>
                <button
                  type="button"
                  onClick={() => setBrand(b)}
                  aria-pressed={brand?.id === b.id}
                  className="rounded-full border border-line px-3 py-1 text-xs hover:border-accent/60 aria-pressed:border-accent aria-pressed:bg-accent-soft aria-pressed:text-accent"
                >
                  {b.name}
                  {!b.claimed && " · not on DealMeet"}
                </button>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <Label htmlFor="np-lang">Language</Label>
          <Select id="np-lang" value={lang} onChange={(e) => setLang(e.target.value as WriteLang)} className="min-w-40">
            {WRITE_LANGS.map((l) => (
              <option key={l.value} value={l.value}>
                {l.label}
              </option>
            ))}
          </Select>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button variant="primary" disabled={!chosen} loading={write.isPending} onClick={() => write.mutate()}>
          {!write.isPending && <PenLine aria-hidden />} Write my pitch{chosen ? ` to ${chosen.name}` : ""}
        </Button>
        <p className="text-xs text-muted">Written from your own numbers only, in the language you pick. The price range comes from your fair-rate estimate, never from the pitch writer.</p>
      </div>
    </section>
  );
}

function Editor({ creatorId, pitch, onDone }: { creatorId: string; pitch: Pitch; onDone: () => void }) {
  const [subject, setSubject] = useState(pitch.subject);
  const [body, setBody] = useState(pitch.pitch);
  const [ideas, setIdeas] = useState(pitch.content_ideas);
  const [confirm, setConfirm] = useState(false);
  const words = body.trim().split(/\s+/).filter(Boolean).length;
  const dirty = subject !== pitch.subject || body !== pitch.pitch || ideas.some((x, i) => x !== pitch.content_ideas[i]);
  const saveIt = () => api<Pitch>(`/creators/${creatorId}/pitches/${pitch.id}`, { method: "PATCH", json: { subject, pitch: body, content_ideas: ideas } });
  const save = useMutation({ mutationFn: saveIt, onSuccess: () => toast.success("Pitch saved"), onError: (e) => toast.error((e as Error).message) });
  const send = useMutation({
    mutationFn: async () => {
      if (dirty) await saveIt();
      return post<Pitch & { left_this_week?: number }>(`/creators/${creatorId}/pitches/${pitch.id}/send`);
    },
    onSuccess: (p) => {
      setConfirm(false);
      toast.success(p.status === "shared" ? "Share link ready" : `Sent to ${pitch.brand_name}`, {
        description: p.status === "shared" ? "Copy it from your pitches and send it yourself." : "It's in their Fan Inbox.",
      });
      onDone();
    },
    onError: (e) => {
      setConfirm(false);
      toast.error((e as Error).message);
    },
  });
  const r = pitch.suggested_price_range;
  return (
    <section aria-labelledby="edit" className="card-surface mt-6 grid gap-5 rounded-[var(--radius-card)] p-5 lg:grid-cols-[1.4fr_1fr]">
      <div className="space-y-3">
        <h2 id="edit" className="flex flex-wrap items-center gap-2 font-display text-lg font-semibold">
          Pitch to {pitch.brand_name}
          <Badge size="sm" variant="outline">{pitch.written_by === "ai" ? "Drafted by AI from your numbers" : "Drafted from a template"}</Badge>
        </h2>
        <div>
          <Label htmlFor="pe-subject">Subject</Label>
          <Input id="pe-subject" value={subject} onChange={(e) => setSubject(e.target.value)} maxLength={90} />
        </div>
        <div>
          <Label htmlFor="pe-body">Pitch</Label>
          <Textarea id="pe-body" value={body} onChange={(e) => setBody(e.target.value)} maxLength={1200} className="min-h-40" lang={htmlLang(pitch.lang)} />
          <FieldHint className={words > 150 ? "text-danger" : undefined}>{words} of 150 words. Numbers must come from your data; promises can't be sent.</FieldHint>
        </div>
        <fieldset className="space-y-2">
          <legend className="mb-1 text-[13px] font-medium text-fg-2">Three content ideas</legend>
          {ideas.map((x, i) => (
            <Input key={i} value={x} onChange={(e) => setIdeas((all) => all.map((y, j) => (j === i ? e.target.value : y)))} maxLength={160} aria-label={`Content idea ${i + 1}`} />
          ))}
        </fieldset>
        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="ghost" onClick={onDone}>
            Close
          </Button>
          <Button variant="outline" disabled={!dirty} loading={save.isPending} onClick={() => save.mutate()}>
            Save
          </Button>
          <Button variant="primary" disabled={words > 150} onClick={() => setConfirm(true)}>
            <Send aria-hidden /> {pitch.on_platform === false ? "Make a share link" : "Send"}
          </Button>
        </div>
      </div>
      <aside className="space-y-4 text-sm">
        {r && (
          <div className="rounded-xl bg-surface-2 p-3">
            <p className="text-xs font-semibold uppercase tracking-[0.1em] text-muted">Suggested price · estimate</p>
            <p className="num mt-1 font-display text-xl font-semibold">{inrRange(r.range.low, r.range.high)}</p>
            <p className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-fg-2">
              {r.deliverables} · {r.data_label} <SourceBadge source={r.data_source} />
            </p>
          </div>
        )}
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.1em] text-muted">Fan Proof</p>
          {pitch.fan_proof ? (
            <p className="mt-1">
              {pitch.fan_proof.label} <SourceBadge source={`${pitch.fan_proof.platforms[0]}_api`} />
            </p>
          ) : (
            <p className="mt-1 text-xs text-muted">None found. Only posts synced from a connected Instagram or YouTube account count, never typed-in ones.</p>
          )}
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.1em] text-muted">Numbers it can use</p>
          <ul className="mt-1.5 divide-y divide-line rounded-xl border border-line">
            {pitch.facts.map((f) => (
              <li key={f.key} className="flex flex-wrap items-center gap-2 px-3 py-1.5 text-xs">
                <span className="flex-1 text-fg-2">{f.label}</span>
                <span className="num font-medium">{f.value}</span>
                <SourceBadge source={f.source} />
              </li>
            ))}
          </ul>
        </div>
      </aside>
      <Dialog open={confirm} onOpenChange={setConfirm}>
        <DialogContent
          title={pitch.on_platform === false ? `Make a share link for ${pitch.brand_name}?` : `Send this pitch to ${pitch.brand_name}?`}
          description={
            pitch.on_platform === false
              ? "They aren't on DealMeet AI, so you'll get a private link to send them yourself. You can turn it off any time. It counts toward your 5 a week."
              : "It goes to their Fan Inbox. It counts toward your 5 pitches a week."
          }
        >
          <p className="rounded-xl bg-surface-2 p-3 text-sm font-medium">{subject}</p>
          <div className="mt-4 flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setConfirm(false)}>
              Not yet
            </Button>
            <Button variant="primary" loading={send.isPending} onClick={() => send.mutate()}>
              {!send.isPending && <Send aria-hidden />} Confirm
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </section>
  );
}

function PitchRow({ p, creatorId, onEdit, onChange }: { p: Pitch; creatorId: string; onEdit: () => void; onChange: () => void }) {
  const revoke = useMutation({ mutationFn: () => post(`/creators/${creatorId}/pitches/${p.id}/revoke`), onSuccess: onChange });
  const remove = useMutation({ mutationFn: () => del(`/creators/${creatorId}/pitches/${p.id}`), onSuccess: onChange });
  const link = p.share && !p.share.revoked ? `${window.location.origin}/p/${p.share.slug}` : null;
  const s = STATUS[p.status];
  return (
    <li className="flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-3">
      <div className="min-w-0 flex-1">
        <p className="flex flex-wrap items-center gap-2 text-sm font-medium">
          {p.brand_name} <Badge size="sm" variant={s.variant}>{s.label}</Badge>
        </p>
        <p className="truncate text-xs text-muted">
          {p.subject} · {p.sent_at ? `sent ${shortDate(p.sent_at)}` : `drafted ${shortDate(p.created_at)}`}
        </p>
      </div>
      {p.status === "draft" && (
        <>
          <Button size="sm" variant="outline" onClick={onEdit}>
            <PenLine aria-hidden /> Edit and send
          </Button>
          <Button size="sm" variant="ghost" onClick={() => remove.mutate()} aria-label={`Delete the draft to ${p.brand_name}`}>
            <Trash2 aria-hidden />
          </Button>
        </>
      )}
      {link && (
        <>
          <Button
            size="sm"
            variant="outline"
            onClick={async () => {
              try {
                await navigator.clipboard.writeText(link);
                toast.success("Link copied");
              } catch {
                toast(link);
              }
            }}
          >
            <Copy aria-hidden /> Copy link
          </Button>
          <Button size="sm" variant="ghost" onClick={() => revoke.mutate()}>
            <X aria-hidden /> Turn off link
          </Button>
        </>
      )}
      {p.share?.revoked && <span className="text-xs text-muted">Link turned off</span>}
      {p.status === "accepted" && p.deal_id && (
        <Button asChild size="sm" variant="outline">
          <Link to={`/creator/deals/${p.deal_id}`}>
            <Link2 aria-hidden /> Open the offer
          </Link>
        </Button>
      )}
    </li>
  );
}
