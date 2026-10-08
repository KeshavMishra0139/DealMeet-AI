import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BadgeCheck, Ban, Download, Eye, Instagram, KeyRound, Settings2, ShieldCheck, ShieldOff, UserCheck, Youtube } from "lucide-react";
import { toast } from "sonner";
import { Avatar, ErrorState, SectionTitle } from "@/components/shared/Bits";
import { ScopePicker } from "@/components/shared/ScopePicker";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton, Switch } from "@/components/ui/form";
import { useI18n } from "@/i18n";
import { api } from "@/lib/api";
import { shortDate, timeOfDay } from "@/lib/format";
import type { Privacy as PrivacyData, Scopes } from "@/lib/market-types";
import { useCreatorId } from "@/lib/session";
import { cn } from "@/lib/utils";

const ACTION = {
  granted: { label: "Access granted", icon: KeyRound, tone: "text-success" },
  updated: { label: "Access updated", icon: Settings2, tone: "text-accent" },
  revoked: { label: "Access revoked", icon: ShieldOff, tone: "text-danger" },
  viewed: { label: "Viewed your profile", icon: Eye, tone: "text-muted" },
  requested: { label: "Asked for more access", icon: UserCheck, tone: "text-warn" },
  declined: { label: "Request declined", icon: Ban, tone: "text-muted" },
  settings: { label: "Default settings changed", icon: Settings2, tone: "text-accent" },
} as const;

export default function Privacy() {
  const id = useCreatorId();
  const { t } = useI18n();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["privacy", id], queryFn: () => api<PrivacyData>(`/creators/${id}/privacy`) });
  const save = (path: string, body?: unknown, method: "POST" | "DELETE" = "POST") =>
    api<PrivacyData>(`/creators/${id}${path}`, { method, json: body ?? (method === "POST" ? {} : undefined) });
  const mutate = useMutation({
    mutationFn: ({ path, body, method }: { path: string; body?: unknown; method?: "POST" | "DELETE" }) => save(path, body, method),
    onSuccess: (data) => {
      qc.setQueryData(["privacy", id], data);
      qc.invalidateQueries({ queryKey: ["opps", id] });
    },
  });

  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data) return <Skeleton className="h-96 rounded-[var(--radius-card)]" />;
  const p = q.data;

  return (
    <div>
      <h1 className="font-display text-[28px] font-semibold tracking-tight sm:text-[34px]">{t("privacy.title")}</h1>
      <p className="mt-1 text-[15px] text-fg-2">You decide who finds you and exactly what each of them sees.</p>

      <div className="mt-6 grid gap-3 lg:grid-cols-2">
        <section aria-labelledby="disc" className="card-surface rounded-[var(--radius-card)] p-5">
          <SectionTitle id="disc" eyebrow="Visibility" title="Who can find you" />
          <label className="flex items-center justify-between gap-4 rounded-2xl bg-surface-2 p-3.5">
            <span>
              <span className="block font-medium">Discoverable to brands and pages</span>
              <span className="block text-xs text-muted">{p.discoverable ? "You appear in matches and collectives." : "Hidden from every brand search and collective."}</span>
            </span>
            <Switch
              checked={p.discoverable}
              onCheckedChange={(v) => mutate.mutate({ path: "/privacy", body: { discoverable: v } })}
              aria-label="Discoverable to brands and pages"
            />
          </label>
          <p className="mb-2 mt-5 text-xs font-semibold uppercase tracking-[0.1em] text-muted">What brands see by default</p>
          <ScopePicker
            value={p.defaults as Scopes}
            disabled={!p.discoverable}
            onChange={(v) => mutate.mutate({ path: "/privacy", body: { defaults: v } })}
          />
          <p className="mt-2 text-xs text-muted">Per-brand choices below override these defaults.</p>
        </section>

        <section aria-labelledby="sources" className="card-surface rounded-[var(--radius-card)] p-5">
          <SectionTitle id="sources" eyebrow="Data sources" title="Where your numbers come from" />
          <ul className="space-y-2">
            {p.sources.map((s) => {
              const Icon = s.platform === "instagram" ? Instagram : Youtube;
              return (
                <li key={s.platform} className="flex items-center gap-3 rounded-2xl bg-surface-2 p-3.5">
                  <Icon className="size-5" aria-hidden />
                  <span className="flex-1">
                    <span className="block text-sm font-medium capitalize">{s.platform}</span>
                    <span className="block text-xs text-muted">{s.connected ? s.via : "Not connected"}</span>
                  </span>
                  {s.connected ? <Badge size="sm" variant="success">Connected</Badge> : <Badge size="sm">Off</Badge>}
                </li>
              );
            })}
          </ul>
          <p className="mt-3 flex gap-2 text-[13px] leading-relaxed text-fg-2">
            <ShieldCheck className="mt-0.5 size-4 shrink-0 text-success" aria-hidden />
            JodiDar uses only what you connect through official logins, what you type, and what you upload. We never scrape, and we never
            read accounts that haven't connected.
          </p>
          {p.is_reference && (
            <p className="mt-2 text-xs text-muted">This reference profile's connected data is partly simulated for the demo.</p>
          )}
          <Button asChild variant="outline" size="sm" className="mt-4">
            <a href={`/api/creators/${id}/export`} download={`jodidar-${id}.json`}>
              <Download aria-hidden /> Download my data
            </a>
          </Button>
        </section>
      </div>

      {p.requests.length > 0 && (
        <section aria-labelledby="reqs" className="mt-6">
          <SectionTitle id="reqs" eyebrow="Waiting for you" title="Access requests" />
          <ul className="space-y-2">
            {p.requests.map((r) => (
              <li key={r.id} className="card-surface flex flex-wrap items-center gap-3 rounded-2xl p-4">
                <UserCheck className="size-5 text-warn" aria-hidden />
                <p className="min-w-0 flex-1 text-sm">
                  <span className="font-medium">{r.lister}</span> asked to see{" "}
                  {r.scopes.map((s) => p.scope_labels[s as keyof Scopes]?.toLowerCase()).join(" and ")}.
                </p>
                <Button size="sm" variant="ghost" onClick={() => mutate.mutate({ path: `/requests/${r.id}`, body: { answer: "decline" } })}>
                  Decline
                </Button>
                <Button
                  size="sm"
                  variant="primary"
                  onClick={() => {
                    mutate.mutate({ path: `/requests/${r.id}`, body: { answer: "approve" } });
                    toast.success(`${r.lister} can now see it`);
                  }}
                >
                  Allow
                </Button>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section aria-labelledby="grants" className="mt-8">
        <SectionTitle id="grants" eyebrow="Per lister" title="Who can see what" />
        {p.grants.length === 0 ? (
          <p className="text-sm text-muted">No one has extra access yet. Applying to an opportunity lets you choose what that lister sees.</p>
        ) : (
          <ul className="space-y-3">
            {p.grants.map((g) => (
              <li key={g.lister_id} className={cn("card-surface rounded-[var(--radius-card)] p-4", g.status === "revoked" && "border-dashed")}>
                <div className="flex flex-wrap items-center gap-3">
                  <Avatar name={g.lister} hue={g.lister.length * 37} size={36} className="rounded-xl" />
                  <div className="min-w-0 flex-1">
                    <p className="flex flex-wrap items-center gap-1.5 font-medium">
                      {g.lister}
                      {g.status === "revoked" && <Badge size="sm" variant="danger">Revoked</Badge>}
                      {g.verified ? <BadgeCheck className="size-3.5 text-accent" aria-label="Verified" /> : <Badge size="sm" variant="warn">Unverified</Badge>}
                    </p>
                    <p className="text-xs text-muted">
                      {g.status === "revoked"
                        ? `Revoked ${g.revoked_at ? shortDate(g.revoked_at) : ""}. They can't find you.`
                        : `Granted ${g.granted_at ? shortDate(g.granted_at) : ""}`}
                    </p>
                  </div>
                  {g.status === "active" ? (
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={() => {
                        mutate.mutate({ path: `/consents/${g.lister_id}`, method: "DELETE" });
                        toast(`${g.lister} can no longer see your profile`);
                      }}
                    >
                      Revoke
                    </Button>
                  ) : (
                    <Button variant="outline" size="sm" onClick={() => mutate.mutate({ path: `/consents/${g.lister_id}`, body: { scopes: { stats: true, demographics: false, rate_card: false } } })}>
                      Restore
                    </Button>
                  )}
                </div>
                {g.status === "active" && (
                  <div className="mt-3">
                    <ScopePicker compact value={g.scopes} onChange={(v) => mutate.mutate({ path: `/consents/${g.lister_id}`, body: { scopes: v } })} />
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="audit" className="mt-8">
        <SectionTitle id="audit" eyebrow="Audit trail" title="Every grant, revoke and view" />
        <ol className="card-surface divide-y divide-line rounded-[var(--radius-card)]">
          {p.audit.map((a) => {
            const meta = ACTION[a.action as keyof typeof ACTION] ?? ACTION.updated;
            return (
              <li key={a.id} className="flex items-start gap-3 px-4 py-3">
                <meta.icon className={cn("mt-0.5 size-4 shrink-0", meta.tone)} aria-hidden />
                <div className="min-w-0 flex-1 text-sm">
                  <p>
                    <span className="font-medium">{a.lister === "Unknown lister" ? "You" : a.lister}</span>{" "}
                    <span className="text-fg-2">{meta.label.toLowerCase()}</span>
                  </p>
                  {a.scopes.length > 0 && (
                    <p className="text-xs text-muted">{a.scopes.map((s) => p.scope_labels[s as keyof Scopes] ?? s).join(", ")}</p>
                  )}
                </div>
                <time className="num shrink-0 text-xs text-muted" dateTime={a.at}>
                  {shortDate(a.at)} · {timeOfDay(a.at)}
                </time>
              </li>
            );
          })}
        </ol>
      </section>
    </div>
  );
}
