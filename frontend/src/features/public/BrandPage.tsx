import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, BadgeCheck, Building2, ExternalLink, Flag, Globe, Heart, KeyRound, Megaphone, Send, Users } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";
import { Avatar, ErrorState } from "@/components/shared/Bits";
import { ReportButton } from "@/components/shared/ReportButton";
import { SourceBadge } from "@/components/shared/SourceBadge";
import { Wordmark } from "@/components/shared/Wordmark";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { FieldHint, Input, Label, Skeleton, Switch, Textarea } from "@/components/ui/form";
import { Dialog, DialogContent } from "@/components/ui/overlays";
import { api, post } from "@/lib/api";
import { deliverable, shortDate } from "@/lib/format";
import { hasDemoSession, useSession, type Role } from "@/lib/session";
import { useTheme } from "@/lib/theme";
import type { BrandCard } from "./Brands";
import NotFound from "./NotFound";

interface Page extends BrandCard {
  owner: boolean;
  description?: string;
  website?: string | null;
  campaigns?: { id: string; title: string; type: string; deadline: string | null; budget: string | null; deliverables: { kind: string; count: number }[] }[];
  dream: { connected: number; others: number; names?: { id: string; name: string; handle: string }[] };
  viewer: { role?: "creator" | "brand"; creator_id?: string; saved?: boolean; show_name?: boolean; can_claim?: boolean; claim?: string | null };
}

/** A brand's page: open campaigns, or for an unclaimed brand only its public basics. */
export default function BrandPage() {
  useTheme("creator");
  const { slug = "" } = useParams();
  // Demo sessions are signed in first; a real account's cookie travels with the request
  // and the server says who is viewing.
  const creator = useSession("creator", hasDemoSession("creator"));
  const brand = useSession("brand", !hasDemoSession("creator") && hasDemoSession("brand"));
  const role: Role | null = creator.data?.user.role === "creator" ? "creator" : brand.data?.user.role === "brand" ? "brand" : null;
  const ready = !creator.isFetching && !brand.isFetching;
  const q = useQuery({
    queryKey: ["brand-page", slug, role],
    queryFn: () => api<Page>(`/directory/brands/${slug}`, { role }),
    enabled: ready,
    retry: false,
  });
  if (q.isError && (q.error as { status?: number }).status === 404) return <NotFound />;
  const p = q.data;

  return (
    <div className="theme-creator grain relative min-h-dvh">
      <div className="aurora" aria-hidden>
        <span />
      </div>
      <div className="relative z-10 mx-auto max-w-3xl px-4 py-6 sm:py-10">
        <header className="flex items-center justify-between gap-3">
          <Link to="/" aria-label="JodiDar AI home" className="rounded-lg">
            <Wordmark />
          </Link>
          <Link to="/brands" className="inline-flex items-center gap-1 text-xs font-medium text-muted hover:text-fg">
            <ArrowLeft className="size-3.5" aria-hidden /> All brands
          </Link>
        </header>
        <main id="main" className="mt-8">
          {q.isError && <ErrorState error={q.error} onRetry={() => q.refetch()} />}
          {!p && !q.isError && <Skeleton className="h-96 rounded-[28px]" />}
          {p && (
            <article className="card-surface rounded-[28px] p-6">
              <div className="flex flex-wrap items-center gap-4">
                {p.claimed ? (
                  <Avatar name={p.name} hue={p.hue ?? 260} size={64} className="rounded-2xl" />
                ) : (
                  <span className="grid size-16 place-items-center rounded-2xl border border-dashed border-line-strong text-muted" aria-hidden>
                    <Building2 className="size-7" />
                  </span>
                )}
                <div className="min-w-0 flex-1">
                  <h1 className="flex flex-wrap items-center gap-2 font-display text-2xl font-semibold">
                    {p.name} {p.verified && <BadgeCheck className="size-5 text-accent" aria-label="Verified" />}
                  </h1>
                  <p className="flex flex-wrap items-center gap-2 text-sm text-muted">
                    {p.category} {!p.claimed && <Badge size="sm" variant="outline">Unclaimed</Badge>} <SourceBadge source={p.source} />
                  </p>
                </div>
                {p.viewer.role === "creator" && p.viewer.creator_id && (
                  <div className="flex flex-col items-end gap-2">
                    <DreamButton page={p} creatorId={p.viewer.creator_id} />
                    <Button asChild size="sm" variant="outline">
                      <Link to={`/creator/pitches?brand=${p.id}&name=${encodeURIComponent(p.name)}`}>
                        <Send aria-hidden /> Pitch this brand
                      </Link>
                    </Button>
                  </div>
                )}
              </div>

              {!p.claimed && (
                <p role="note" className="mt-5 rounded-xl border border-warn/40 bg-warn-soft p-3 text-sm">
                  <span className="font-medium">{p.note}</span> This page lists only public information so creators can save it. If this is your brand, you can claim it.
                </p>
              )}
              {p.claimed && p.description && <p className="mt-5 text-[15px] leading-relaxed text-fg-2">{p.description}</p>}
              <div className="mt-4 flex flex-wrap gap-2 text-sm">
                {p.website && (
                  <a href={p.website} target="_blank" rel="noreferrer nofollow" className="inline-flex items-center gap-1.5 text-accent hover:underline">
                    <Globe className="size-4" aria-hidden /> Website <ExternalLink className="size-3" aria-hidden />
                  </a>
                )}
                {p.public_handles?.instagram && <Badge size="sm">Instagram {p.public_handles.instagram}</Badge>}
                {p.public_handles?.youtube && <Badge size="sm">YouTube {p.public_handles.youtube}</Badge>}
              </div>

              <section aria-labelledby="dream" className="mt-6 rounded-xl bg-surface-2 p-4">
                <h2 id="dream" className="flex items-center gap-1.5 text-sm font-semibold">
                  <Users className="size-4 text-accent" aria-hidden /> {p.dream.connected} creator{p.dream.connected === 1 ? "" : "s"} with connected accounts want to work with {p.owner ? "you" : "this brand"}
                </h2>
                {p.dream.others > 0 && <p className="mt-0.5 text-xs text-muted">Plus {p.dream.others} without a connected account.</p>}
                {p.owner && p.dream.names && (
                  <p className="mt-2 text-xs text-fg-2">
                    {p.dream.names.length ? `Who agreed to show their name: ${p.dream.names.map((n) => n.name).join(", ")}.` : "Nobody has agreed to show their name yet."}
                  </p>
                )}
              </section>

              {p.claimed && (
                <section aria-labelledby="open" className="mt-6">
                  <h2 id="open" className="flex items-center gap-1.5 font-display text-lg font-semibold">
                    <Megaphone className="size-4 text-accent" aria-hidden /> Open campaigns
                  </h2>
                  {p.campaigns && p.campaigns.length > 0 ? (
                    <ul className="mt-3 divide-y divide-line rounded-xl border border-line">
                      {p.campaigns.map((c) => (
                        <li key={c.id} className="px-4 py-3">
                          <p className="font-medium">{c.title}</p>
                          <p className="text-xs text-muted">
                            {c.deliverables.map(deliverable).join(", ")}
                            {c.budget && ` · ${c.budget}`}
                            {c.deadline && ` · until ${shortDate(c.deadline)}`}
                          </p>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-2 text-sm text-muted">No open campaigns right now. Save this brand to hear when one opens.</p>
                  )}
                  {p.viewer.role === "creator" && (p.campaigns?.length ?? 0) > 0 && (
                    <Button asChild size="sm" variant="outline" className="mt-3">
                      <Link to="/creator/opportunities">Apply from your opportunities</Link>
                    </Button>
                  )}
                </section>
              )}

              {!p.claimed && (
                <div className="mt-6 flex flex-wrap gap-2 border-t border-line pt-4">
                  {p.viewer.role === "brand" && <ClaimButton page={p} />}
                  {p.viewer.role !== "brand" && (
                    <Button asChild size="sm" variant="outline">
                      <Link to="/login?role=brand">
                        <KeyRound aria-hidden /> Is this your brand? Sign in to claim it
                      </Link>
                    </Button>
                  )}
                  <RemovalButton page={p} />
                </div>
              )}
              {p.claimed && !p.owner && (
                <div className="mt-6 flex justify-end border-t border-line pt-3">
                  <ReportButton type="profile" id={p.id} role={role} label="Report this brand" />
                </div>
              )}
            </article>
          )}
        </main>
      </div>
    </div>
  );
}

function DreamButton({ page, creatorId }: { page: Page; creatorId: string }) {
  const qc = useQueryClient();
  const [showName, setShowName] = useState(!!page.viewer.show_name);
  const save = useMutation({
    mutationFn: (v: { saved: boolean; show_name: boolean }) =>
      v.saved
        ? api(`/creators/${creatorId}/dream-brands/${page.id}`, { method: "PUT", json: { show_name: v.show_name }, role: "creator" })
        : api(`/creators/${creatorId}/dream-brands/${page.id}`, { method: "DELETE", role: "creator" }),
    onSuccess: (_, v) => {
      void qc.invalidateQueries({ queryKey: ["brand-page"] });
      void qc.invalidateQueries({ queryKey: ["dream", creatorId] });
      toast.success(v.saved ? `${page.name} saved to your Dream Brands` : "Removed from your Dream Brands", {
        description: v.saved ? "We'll tell you when they open a campaign." : undefined,
      });
    },
    onError: (e) => toast.error((e as Error).message),
  });
  const saved = !!page.viewer.saved;
  return (
    <div className="flex flex-col items-end gap-2">
      <Button variant={saved ? "outline" : "primary"} loading={save.isPending} onClick={() => save.mutate({ saved: !saved, show_name: showName })} aria-pressed={saved}>
        {!save.isPending && <Heart aria-hidden className={saved ? "fill-current" : undefined} />} {saved ? "Saved" : "Save as Dream Brand"}
      </Button>
      <label className="flex items-center gap-2 text-xs text-fg-2">
        <Switch
          checked={showName}
          onCheckedChange={(v) => {
            setShowName(v);
            if (saved) save.mutate({ saved: true, show_name: v });
          }}
          aria-label="Let this brand see my name"
        />
        Let this brand see my name
      </label>
    </div>
  );
}

function ClaimButton({ page }: { page: Page }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("");
  const claim = useMutation({
    mutationFn: () => api<{ status: string }>(`/directory/brands/${page.slug}/claim`, { method: "POST", json: { message }, role: "brand" }),
    onSuccess: () => {
      setOpen(false);
      void qc.invalidateQueries({ queryKey: ["brand-page"] });
      toast.success("Claim sent", { description: "An admin checks it. Until then the page stays unclaimed." });
    },
    onError: (e) => toast.error((e as Error).message),
  });
  if (page.viewer.claim === "pending") return <Badge variant="accent">Your claim is waiting for an admin</Badge>;
  if (!page.viewer.can_claim) return <p className="text-xs text-muted">This account already manages a brand. Claim with the account that should own this page.</p>;
  return (
    <>
      <Button size="sm" variant="primary" onClick={() => setOpen(true)}>
        <KeyRound aria-hidden /> Claim this page
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent title={`Claim ${page.name}`} description="Tell us how you're connected to this brand. An admin approves claims; nothing changes until then.">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              claim.mutate();
            }}
          >
            <Label htmlFor="claim-msg">How you're connected</Label>
            <Textarea id="claim-msg" value={message} onChange={(e) => setMessage(e.target.value)} minLength={10} maxLength={600} required />
            <FieldHint>For example, your role and a work email on the brand's domain.</FieldHint>
            <div className="mt-4 flex justify-end">
              <Button type="submit" variant="primary" loading={claim.isPending} disabled={message.trim().length < 10}>
                Send claim
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}

function RemovalButton({ page }: { page: Page }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [contact, setContact] = useState("");
  const send = useMutation({
    mutationFn: () => post(`/directory/brands/${page.slug}/removal-request`, { reason, contact: contact || null }),
    onSuccess: () => {
      setOpen(false);
      toast.success("Removal request sent", { description: "An admin reviews it." });
    },
    onError: (e) => toast.error((e as Error).message),
  });
  return (
    <>
      <Button size="sm" variant="ghost" onClick={() => setOpen(true)}>
        <Flag aria-hidden /> Request removal
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent title="Ask us to remove this page" description="Anyone can ask. An admin reviews each request.">
          <form
            className="space-y-3"
            onSubmit={(e) => {
              e.preventDefault();
              send.mutate();
            }}
          >
            <div>
              <Label htmlFor="rm-reason">Why it should be removed</Label>
              <Textarea id="rm-reason" value={reason} onChange={(e) => setReason(e.target.value)} minLength={10} maxLength={600} required />
            </div>
            <div>
              <Label htmlFor="rm-contact">Email for a reply (optional)</Label>
              <Input id="rm-contact" type="email" value={contact} onChange={(e) => setContact(e.target.value)} maxLength={120} />
              <FieldHint>Only admins see it.</FieldHint>
            </div>
            <div className="flex justify-end">
              <Button type="submit" variant="primary" loading={send.isPending} disabled={reason.trim().length < 10}>
                Send request
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
