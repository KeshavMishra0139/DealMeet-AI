import { useQuery } from "@tanstack/react-query";
import { AlertCircle, ArrowRight, CircleDollarSign, Clock, Lock, Megaphone, Plus, Users } from "lucide-react";
import { Link } from "react-router-dom";
import { motion, useReducedMotion } from "framer-motion";
import { CountUp, Reveal, Stagger, StaggerItem, TiltCard } from "@/components/motion/Motion";
import { Stage3D } from "@/components/three/Stage3D";
import { DealFlow3D } from "@/components/three/lazy";
import { Avatar, EmptyState, ErrorState } from "@/components/shared/Bits";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/form";
import { api } from "@/lib/api";
import { inr, inrShort, shortDate } from "@/lib/format";
import type { Console } from "@/lib/market-types";
import { useBrandId } from "@/lib/session";
import { cn } from "@/lib/utils";

export const TYPE_LABEL: Record<string, string> = {
  brand_campaign: "Campaign",
  collective: "Collective",
  pr_service: "PR brief",
  page: "Page feature",
  creator_collab: "Collab",
};

export function useConsole(id: string) {
  return useQuery({ queryKey: ["console", id], queryFn: () => api<Console>(`/brands/${id}/console`) });
}

export default function BrandHome() {
  const id = useBrandId();
  const q = useConsole(id);
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data) return <ConsoleSkeleton />;
  const d = q.data;
  const live = d.campaigns.filter((c) => c.status === "open");
  const maxCount = Math.max(1, ...d.stages.map((s) => s.count));

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs font-medium text-muted">Overview · {d.brand.category}</p>
          <h1 className="mt-1 font-display text-2xl font-semibold tracking-tight">{d.brand.name}</h1>
          <p className="mt-1 text-sm text-fg-2">{d.headline}</p>
        </div>
        <Button asChild variant="primary" size="sm">
          <Link to="/brand/campaigns/new">
            <Plus aria-hidden /> New campaign
          </Link>
        </Button>
      </div>

      <section aria-label="Key numbers" className="mt-6">
        <Stagger className="grid gap-3 md:grid-cols-3">
          <StaggerItem>
            <TiltCard className="h-full rounded-xl" max={4}>
              <div className="card-surface h-full rounded-xl p-4">
                <p className="flex items-center gap-1.5 text-xs font-medium text-muted">
                  <Megaphone className="size-3.5" aria-hidden /> Active campaigns
                </p>
                <p className="num mt-2 font-display text-[28px] font-semibold leading-none">
                  <CountUp value={live.length} format={String} />
                </p>
                <ul className="mt-3 space-y-1.5 text-[13px]">
                  {live.slice(0, 3).map((c) => (
                    <li key={c.id} className="flex items-center justify-between gap-2">
                      <Link to={`/brand/campaigns/${c.id}`} className="truncate text-fg-2 hover:text-accent">
                        {c.title}
                      </Link>
                      <span className="num shrink-0 text-xs text-muted">{c.applications} applied</span>
                    </li>
                  ))}
                </ul>
              </div>
            </TiltCard>
          </StaggerItem>

          <StaggerItem>
            <TiltCard className="h-full rounded-xl" max={4}>
              <div className="card-surface h-full rounded-xl p-4">
                <p className="flex items-center gap-1.5 text-xs font-medium text-muted">
                  <Lock className="size-3.5" aria-hidden /> Held in escrow
                </p>
                <p className="num mt-2 font-display text-[28px] font-semibold leading-none">
                  <CountUp value={d.escrow.held} format={inr} />
                </p>
                <p className="mt-1 text-xs text-muted">
                  Across {d.escrow.count} deal{d.escrow.count === 1 ? "" : "s"} · {inrShort(d.paid_total)} paid out so far
                </p>
                <ul className="mt-3 space-y-1.5 text-[13px]">
                  {d.escrow.items.slice(0, 3).map((e) => (
                    <li key={e.deal_id} className="flex items-center justify-between gap-2">
                      <span className="truncate text-fg-2">{e.creator}</span>
                      <span className="flex shrink-0 items-center gap-2">
                        <Badge size="sm" variant="outline">
                          {e.stage_label}
                        </Badge>
                        <span className="num font-medium">{inrShort(e.amount)}</span>
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            </TiltCard>
          </StaggerItem>

          <StaggerItem>
            <TiltCard className="h-full rounded-xl" max={4}>
              <div className="card-surface h-full rounded-xl p-4">
                <p className="flex items-center gap-1.5 text-xs font-medium text-muted">
                  <CircleDollarSign className="size-3.5" aria-hidden /> Deals by stage
                </p>
                <ol className="mt-3 space-y-1.5">
                  {d.stages.map((s) => (
                    <li key={s.stage} className="grid grid-cols-[96px_1fr_auto] items-center gap-2 text-[13px]">
                      <span className="text-fg-2">{s.label}</span>
                      <span className="h-1.5 overflow-hidden rounded-full bg-surface-2" aria-hidden>
                        <GrowBar pct={(s.count / maxCount) * 100} />
                      </span>
                      <span className="num w-16 text-right">
                        <span className="font-semibold">{s.count}</span>
                        {s.amount > 0 && <span className="ml-1 text-xs text-muted">{inrShort(s.amount)}</span>}
                      </span>
                    </li>
                  ))}
                </ol>
              </div>
            </TiltCard>
          </StaggerItem>
        </Stagger>
      </section>

      <DealFlow stages={d.stages} />

      {d.needs_you.length > 0 && (
        <Reveal as="section" aria-labelledby="needs" className="mt-6">
          <h2 id="needs" className="mb-2 text-sm font-semibold">
            Needs you
          </h2>
          <ul className="card-surface divide-y divide-line rounded-xl">
            {d.needs_you.map((n) => (
              <li key={n.deal_id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                {n.urgent ? <AlertCircle className="size-4 text-danger" aria-hidden /> : <Clock className="size-4 text-warn" aria-hidden />}
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">{n.text}</p>
                  <p className="text-xs text-muted">{n.detail}</p>
                </div>
                <Button asChild size="sm" variant={n.urgent ? "primary" : "outline"}>
                  <Link to={`/brand/deals/${n.deal_id}`}>
                    {n.kind === "confirm" ? "Review post" : "Open"} <ArrowRight aria-hidden />
                  </Link>
                </Button>
              </li>
            ))}
          </ul>
        </Reveal>
      )}

      <section aria-labelledby="camps" className="mt-6">
        <div className="mb-2 flex items-center justify-between">
          <h2 id="camps" className="text-sm font-semibold">
            Campaigns
          </h2>
          <Link to="/brand/campaigns" className="text-xs font-medium text-accent hover:underline">
            View all
          </Link>
        </div>
        {d.campaigns.length === 0 ? (
          <div className="card-surface rounded-xl">
            <EmptyState
              icon={<Megaphone className="size-5" />}
              title="No campaigns yet"
              body="Describe what you need and we'll rank creators who fit, with a fair price for each."
              action={
                <Button asChild variant="primary" size="sm">
                  <Link to="/brand/campaigns/new">Create a campaign</Link>
                </Button>
              }
            />
          </div>
        ) : (
          <CampaignTable campaigns={d.campaigns} />
        )}
      </section>

      <section aria-labelledby="recent" className="mt-6">
        <h2 id="recent" className="mb-2 text-sm font-semibold">
          Recent deal activity
        </h2>
        <ul className="card-surface divide-y divide-line rounded-xl">
          {d.recent.map((r) => (
            <li key={r.deal_id}>
              <Link to={`/brand/deals/${r.deal_id}`} className="flex items-center gap-3 px-4 py-2.5 hover:bg-surface-2">
                <Avatar name={r.creator} hue={r.avatar_hue} size={28} generic={r.is_reference} />
                <span className="min-w-0 flex-1 truncate text-sm">
                  {r.creator}
                  {r.kind === "collective" && <span className="ml-1.5 text-xs text-muted">· collective</span>}
                </span>
                <Badge size="sm" variant={r.stage === "paid" ? "success" : r.stage === "live" ? "warn" : "neutral"}>
                  {r.stage_label}
                </Badge>
                <span className="num hidden w-20 text-right text-sm font-medium sm:block">{inr(r.amount)}</span>
                <span className="num hidden w-16 text-right text-xs text-muted md:block">{r.updated ? shortDate(r.updated) : ""}</span>
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

export function CampaignTable({ campaigns }: { campaigns: Console["campaigns"] }) {
  return (
    <div className="card-surface overflow-hidden rounded-xl">
      <table className="w-full text-left text-[13px]">
        <thead className="border-b border-line bg-surface-2 text-xs text-muted">
          <tr>
            <th scope="col" className="px-4 py-2 font-medium">
              Campaign
            </th>
            <th scope="col" className="hidden px-3 py-2 font-medium md:table-cell">
              Type
            </th>
            <th scope="col" className="hidden px-3 py-2 text-right font-medium sm:table-cell">
              In pool
            </th>
            <th scope="col" className="px-3 py-2 text-right font-medium">
              Applied
            </th>
            <th scope="col" className="hidden px-3 py-2 text-right font-medium sm:table-cell">
              Committed
            </th>
            <th scope="col" className="hidden px-4 py-2 text-right font-medium lg:table-cell">
              Deadline
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {campaigns.map((c) => (
            <tr key={c.id} className="group hover:bg-surface-2">
              <td className="px-4 py-2.5">
                <Link to={`/brand/campaigns/${c.id}`} className="font-medium text-fg group-hover:text-accent">
                  {c.title}
                </Link>
                <span className="block text-xs text-muted">{c.languages.join(", ")}</span>
              </td>
              <td className="hidden px-3 py-2.5 md:table-cell">
                <Badge size="sm" variant={c.type === "collective" ? "accent" : "neutral"}>
                  {c.type === "collective" && <Users aria-hidden />}
                  {TYPE_LABEL[c.type] ?? c.type}
                  {c.deal_kind === "affiliate" && " · affiliate"}
                </Badge>
              </td>
              <td className="num hidden px-3 py-2.5 text-right sm:table-cell">{c.candidates}</td>
              <td className="num px-3 py-2.5 text-right">{c.applications}</td>
              <td className={cn("num hidden px-3 py-2.5 text-right sm:table-cell", !c.committed && "text-muted")}>
                {c.committed ? inr(c.committed) : "—"}
              </td>
              <td className="num hidden px-4 py-2.5 text-right text-muted lg:table-cell">{c.deadline ? shortDate(c.deadline) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ConsoleSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading">
      <Skeleton className="h-4 w-40" />
      <Skeleton className="mt-2 h-7 w-56" />
      <div className="mt-6 grid gap-3 md:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-44 rounded-xl" />
        ))}
      </div>
      <Skeleton className="mt-6 h-56 rounded-xl" />
    </div>
  );
}

/** A bar that grows to its width when it scrolls into view. */
function GrowBar({ pct }: { pct: number }) {
  const reduce = useReducedMotion();
  if (reduce) return <span className="block h-full rounded-full bg-accent" style={{ width: `${pct}%` }} />;
  return (
    <motion.span
      className="block h-full rounded-full bg-accent"
      initial={{ width: 0 }}
      whileInView={{ width: `${pct}%` }}
      viewport={{ once: true }}
      transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
    />
  );
}

/** The deal rail in 3D: where every deal sits, and money flowing from offer to UPI payout. */
function DealFlow({ stages }: { stages: Console["stages"] }) {
  const reduce = useReducedMotion();
  const total = stages.reduce((n, s) => n + s.count, 0);
  if (!total) return null;
  const flow = stages.map((s) => ({ label: s.label, count: s.count, amountLabel: s.amount ? inrShort(s.amount) : null }));
  const summary = stages.map((s) => `${s.label}: ${s.count}`).join(", ");
  return (
    <Reveal as="section" aria-labelledby="flow" className="card-surface mt-3 overflow-hidden rounded-xl">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-2.5">
        <h2 id="flow" className="text-sm font-semibold">
          Deal flow <span className="font-normal text-muted">· escrow before posting, UPI after verification</span>
        </h2>
        <p className="num text-xs text-muted">
          {total} deal{total === 1 ? "" : "s"} on the rail
        </p>
      </div>
      <div className="bg-[linear-gradient(180deg,transparent,rgb(124_58_237/0.05))]">
        <Stage3D className="h-[230px]" label={`3D deal rail. ${summary}.`} fallback={<FlowFallback stages={flow} />}>
          {(active, onScreen) => <DealFlow3D stages={flow} active={active} onScreen={onScreen} still={!!reduce} />}
        </Stage3D>
      </div>
    </Reveal>
  );
}

function FlowFallback({ stages }: { stages: { label: string; count: number; amountLabel: string | null }[] }) {
  return (
    <ol className="flex h-full items-center justify-between gap-2 px-6">
      {stages.map((s) => (
        <li key={s.label} className="text-center text-xs">
          <span className="num mx-auto grid size-9 place-items-center rounded-full border-2 border-accent font-semibold">{s.count}</span>
          <span className="mt-1 block text-fg-2">{s.label}</span>
        </li>
      ))}
    </ol>
  );
}
