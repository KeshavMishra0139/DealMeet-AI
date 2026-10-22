import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, AlertTriangle, Building2, FileUp, Flag, LogOut, Mail, Megaphone, ScrollText, ShieldAlert, Users } from "lucide-react";
import { useDeferredValue, useEffect, useState, type ReactNode } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { EmptyState, ErrorState } from "@/components/shared/Bits";
import { Wordmark } from "@/components/shared/Wordmark";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { FieldHint, Input, Label, Select, Skeleton, Textarea } from "@/components/ui/form";
import { Dialog, DialogContent } from "@/components/ui/overlays";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api, ApiError } from "@/lib/api";
import { shortDate, timeOfDay } from "@/lib/format";
import type { Me } from "@/lib/session";
import { useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";
import { TwoStepGate } from "./TwoStep";

// Admin pages carry no demo token: the session is the HttpOnly cookie, and the server
// checks the admin role on every /api/admin route.
const adminApi = <T,>(path: string, json?: unknown) => api<T>(path, json === undefined ? { role: null } : { method: "POST", json, role: null });

interface Overview {
  accounts: { by_role: Record<string, number>; suspended: number };
  campaigns: Record<string, number>;
  reports: { open: number };
  claims: { pending: number };
  removals: { pending: number };
  locked: { email: string; failures: number }[];
  suspicious: { profile_id: string; open_reports: number }[];
  payments: Record<string, number>;
  payment_events: number;
  connection_errors: { creator_id: string; platform: string; status: string; error: string | null; at: string | null }[];
  health: { status: string; modes?: Record<string, string | boolean>; demo_mode?: boolean };
}

interface Account {
  _id: string;
  role: string;
  name: string | null;
  email: string | null;
  creator_id: string | null;
  brand_id: string | null;
  demo: boolean;
  seeded?: boolean;
  suspended: boolean;
  suspended_reason: string | null;
  created_at: string | null;
}

interface CampaignRow {
  id: string;
  title: string;
  status: string;
  owner: string | null;
  owner_id: string;
  deadline: string | null;
  reports: number;
}

interface Report {
  _id: string;
  target_type: string;
  target_id: string;
  reason: string;
  details: string | null;
  at: string;
  reporter_role: string | null;
  status: string;
  resolution?: string;
  resolution_reason?: string;
}

interface Claim {
  _id: string;
  brand_name: string;
  user_name: string | null;
  user_email: string | null;
  message: string;
  at: string;
}

interface Removal {
  _id: string;
  brand_name: string;
  reason: string;
  contact: string | null;
  at: string;
}

type AuditEvent = { _id: string; at: string; action: string; user_id: string | null; role: string | null } & Record<string, unknown>;

const REASON_LABEL: Record<string, string> = {
  scam_or_fraud: "Scam or fraud",
  fake_numbers: "Fake or inflated numbers",
  spam: "Spam",
  harassment: "Harassment",
  impersonation: "Impersonation",
  inappropriate: "Inappropriate content",
  other: "Something else",
};

const when = (iso: string | null | undefined) => (iso ? `${shortDate(iso)}, ${timeOfDay(iso)}` : "");

/** The admin console. Only an account given the admin role on the server can load anything here. */
export default function AdminConsole() {
  useTheme("brand");
  const me = useQuery({
    queryKey: ["session", "admin"],
    queryFn: async () => {
      try {
        return await api<Me>("/auth/me", { role: null });
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) return null;
        throw e;
      }
    },
  });
  if (me.isPending) return <div className="min-h-dvh" aria-busy="true" aria-label="Checking your sign-in" />;
  if (me.isError)
    return (
      <div className="mx-auto max-w-md p-6">
        <ErrorState error={me.error} onRetry={() => me.refetch()} />
      </div>
    );
  if (!me.data) return <Navigate to="/login?next=%2Fadmin" replace />;
  if (me.data.user.role !== "admin") return <NotAdmin />;
  return (
    <TwoStepGate>
      <Console me={me.data} />
    </TwoStepGate>
  );
}

function NotAdmin() {
  return (
    <div className="theme-brand mx-auto flex min-h-dvh max-w-md flex-col justify-center gap-4 px-5">
      <Wordmark />
      <h1 className="font-display text-2xl font-semibold">Admins only</h1>
      <p className="text-fg-2">This account isn't an admin. The admin role is given on the server by whoever runs DealMeet AI; there's no way to ask for it here.</p>
      <Button asChild variant="outline" className="self-start">
        <Link to="/">Back home</Link>
      </Button>
    </div>
  );
}

const TABS = ["overview", "accounts", "campaigns", "reports", "brands", "audit"];

function Console({ me }: { me: Me }) {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const tab = TABS.includes(params.get("tab") ?? "") ? params.get("tab")! : "overview";
  useEffect(() => {
    // On a phone the tab row scrolls sideways: keep the open tab in view.
    document.querySelector('[role="tab"][data-state="active"]')?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [tab]);
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  const signOut = async () => {
    setBusy(true);
    try {
      await api("/auth/logout", { method: "POST", json: {}, role: null });
    } finally {
      qc.clear();
      navigate("/login");
    }
  };
  return (
    <div className="theme-brand min-h-dvh bg-bg text-fg">
      <header className="sticky top-0 z-20 border-b border-line bg-[var(--surface-solid)]/95 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3">
          <div className="flex items-center gap-3">
            <Wordmark />
            <Badge size="sm" variant="accent">
              Admin
            </Badge>
          </div>
          <div className="flex items-center gap-2 text-sm">
            <span className="hidden text-muted sm:inline">{me.user.name ?? me.user.email}</span>
            <Button size="sm" variant="ghost" onClick={signOut} loading={busy}>
              <LogOut aria-hidden /> Sign out
            </Button>
          </div>
        </div>
      </header>
      <main id="main" className="mx-auto max-w-6xl px-4 py-6">
        <h1 className="font-display text-2xl font-semibold">Admin console</h1>
        <p className="mt-1 text-sm text-muted">Every action here needs a reason and is saved in the audit log.</p>
        <Tabs value={tab} onValueChange={(v) => setParams(v === "overview" ? {} : { tab: v }, { replace: true })} className="mt-5">
          <TabsList aria-label="Admin sections">
            <TabsTrigger value="overview">
              <Activity aria-hidden /> Overview
            </TabsTrigger>
            <TabsTrigger value="accounts">
              <Users aria-hidden /> Accounts
            </TabsTrigger>
            <TabsTrigger value="campaigns">
              <Megaphone aria-hidden /> Campaigns
            </TabsTrigger>
            <TabsTrigger value="reports">
              <Flag aria-hidden /> Reports
            </TabsTrigger>
            <TabsTrigger value="brands">
              <Building2 aria-hidden /> Brand pages
            </TabsTrigger>
            <TabsTrigger value="audit">
              <ScrollText aria-hidden /> Audit log
            </TabsTrigger>
          </TabsList>
          <TabsContent value="overview" className="pt-5">
            <OverviewTab />
          </TabsContent>
          <TabsContent value="accounts" className="pt-5">
            <AccountsTab />
          </TabsContent>
          <TabsContent value="campaigns" className="pt-5">
            <CampaignsTab />
          </TabsContent>
          <TabsContent value="reports" className="pt-5">
            <ReportsTab />
          </TabsContent>
          <TabsContent value="brands" className="pt-5">
            <BrandPagesTab />
          </TabsContent>
          <TabsContent value="audit" className="pt-5">
            <AuditTab />
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}

// ------------------------------------------------------------------ shared bits
function Tile({ label, value, tone }: { label: string; value: ReactNode; tone?: "warn" | "danger" }) {
  return (
    <div className={cn("rounded-2xl border border-line bg-surface p-4", tone === "warn" && "border-warn/50", tone === "danger" && "border-danger/50")}>
      <p className="text-xs text-muted">{label}</p>
      <p className="num mt-1 font-display text-2xl font-semibold">{value}</p>
    </div>
  );
}

function Panel({ title, icon, children }: { title: string; icon?: ReactNode; children: ReactNode }) {
  const id = `p-${title.replace(/\W+/g, "-").toLowerCase()}`;
  return (
    <section aria-labelledby={id} className="rounded-2xl border border-line bg-surface p-4">
      <h2 id={id} className="flex items-center gap-1.5 text-sm font-semibold">
        {icon}
        {title}
      </h2>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function Loading() {
  return <Skeleton className="h-40 rounded-2xl" />;
}

/** Asks for a reason (saved with the decision and in the audit log), then runs the action. */
function ReasonDialog({
  title,
  description,
  confirm,
  danger,
  onClose,
  run,
  children,
}: {
  title: string;
  description: string;
  confirm: string;
  danger?: boolean;
  onClose: () => void;
  run: (reason: string) => Promise<unknown>;
  children?: ReactNode;
}) {
  const qc = useQueryClient();
  const [reason, setReason] = useState("");
  const act = useMutation({
    mutationFn: () => run(reason.trim()),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["admin"] });
      toast.success("Done", { description: "Saved in the audit log with your reason." });
      onClose();
    },
    onError: (e) => toast.error((e as Error).message),
  });
  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent title={title} description={description}>
        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            act.mutate();
          }}
        >
          {children}
          <div>
            <Label htmlFor="admin-reason">Reason</Label>
            <Textarea id="admin-reason" value={reason} onChange={(e) => setReason(e.target.value)} minLength={5} maxLength={300} required className="min-h-20" />
            <FieldHint>At least 5 characters. Saved in the audit log.</FieldHint>
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" variant={danger ? "danger" : "primary"} loading={act.isPending} disabled={reason.trim().length < 5}>
              {confirm}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ------------------------------------------------------------------ overview
function OverviewTab() {
  const q = useQuery({ queryKey: ["admin", "overview"], queryFn: () => adminApi<Overview>("/admin/overview") });
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data) return <Loading />;
  const o = q.data;
  const roles = o.accounts.by_role;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Tile label="Creators" value={roles.creator ?? 0} />
        <Tile label="Brands" value={roles.brand ?? 0} />
        <Tile label="Suspended" value={o.accounts.suspended} tone={o.accounts.suspended ? "warn" : undefined} />
        <Tile label="Open reports" value={o.reports.open} tone={o.reports.open ? "warn" : undefined} />
        <Tile label="Claims waiting" value={o.claims.pending} />
        <Tile label="Removals waiting" value={o.removals.pending} />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="System health" icon={<Activity className="size-4 text-accent" aria-hidden />}>
          <p className="flex items-center gap-2 text-sm">
            <Badge variant={o.health.status === "ok" ? "success" : "danger"}>{o.health.status === "ok" ? "Healthy" : "Database unreachable"}</Badge>
            {o.health.demo_mode && <Badge variant="outline">Demo mode</Badge>}
          </p>
          <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
            {Object.entries(o.health.modes ?? {}).map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="text-muted">{k.replace(/_/g, " ")}</dt>
                <dd className="break-words">{String(v)}</dd>
              </div>
            ))}
          </dl>
        </Panel>
        <Panel title="Campaigns by status" icon={<Megaphone className="size-4 text-accent" aria-hidden />}>
          <ul className="flex flex-wrap gap-2 text-sm">
            {Object.entries(o.campaigns).map(([k, v]) => (
              <li key={k}>
                <Badge>
                  {k}: <span className="num">{v}</span>
                </Badge>
              </li>
            ))}
          </ul>
        </Panel>
        <Panel title="Locked sign-ins (last 15 minutes)" icon={<ShieldAlert className="size-4 text-warn" aria-hidden />}>
          {o.locked.length ? (
            <ul className="space-y-1 text-sm">
              {o.locked.map((l) => (
                <li key={l.email}>
                  {l.email} <span className="text-muted">· {l.failures} wrong passwords</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted">No account is locked out right now.</p>
          )}
        </Panel>
        <Panel title="Reported more than once" icon={<AlertTriangle className="size-4 text-warn" aria-hidden />}>
          {o.suspicious.length ? (
            <ul className="space-y-1 text-sm">
              {o.suspicious.map((s) => (
                <li key={s.profile_id}>
                  <code className="text-xs">{s.profile_id}</code> <span className="text-muted">· {s.open_reports} open reports</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted">No profile has more than one open report.</p>
          )}
        </Panel>
        <Panel title="Payments" icon={<Activity className="size-4 text-accent" aria-hidden />}>
          {Object.keys(o.payments).length ? (
            <ul className="flex flex-wrap gap-2 text-sm">
              {Object.entries(o.payments).map(([k, v]) => (
                <li key={k}>
                  <Badge>
                    {k} · <span className="num">{v}</span>
                  </Badge>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted">No payments recorded yet.</p>
          )}
          <p className="mt-2 text-xs text-muted">Payment webhook events received: {o.payment_events}</p>
        </Panel>
        <Panel title="Connection errors" icon={<AlertTriangle className="size-4 text-warn" aria-hidden />}>
          {o.connection_errors.length ? (
            <ul className="space-y-1.5 text-sm">
              {o.connection_errors.map((c) => (
                <li key={`${c.creator_id}-${c.platform}`}>
                  <span className="font-medium capitalize">{c.platform}</span> <code className="text-xs">{c.creator_id}</code>
                  <span className="text-muted"> · {c.error ?? c.status}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted">No Instagram or YouTube connection is failing.</p>
          )}
        </Panel>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ accounts
function AccountsTab() {
  const [q, setQ] = useState("");
  const [role, setRole] = useState("");
  const [state, setState] = useState("");
  const [acting, setActing] = useState<{ user: Account; suspend: boolean } | null>(null);
  const query = useDeferredValue(q);
  const params = new URLSearchParams();
  if (query.trim()) params.set("q", query.trim());
  if (role) params.set("role", role);
  if (state) params.set("suspended", state);
  const r = useQuery({ queryKey: ["admin", "accounts", params.toString()], queryFn: () => adminApi<{ items: Account[] }>(`/admin/accounts?${params}`), placeholderData: keepPreviousData });
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-[1fr_auto_auto]">
        <div>
          <Label htmlFor="acc-q">Search name, email or id</Label>
          <Input id="acc-q" value={q} onChange={(e) => setQ(e.target.value)} maxLength={60} />
        </div>
        <div>
          <Label htmlFor="acc-role">Role</Label>
          <Select id="acc-role" value={role} onChange={(e) => setRole(e.target.value)}>
            <option value="">All</option>
            <option value="creator">Creators</option>
            <option value="brand">Brands</option>
            <option value="admin">Admins</option>
          </Select>
        </div>
        <div>
          <Label htmlFor="acc-state">State</Label>
          <Select id="acc-state" value={state} onChange={(e) => setState(e.target.value)}>
            <option value="">All</option>
            <option value="true">Suspended</option>
            <option value="false">Active</option>
          </Select>
        </div>
      </div>
      {r.isError && <ErrorState error={r.error} onRetry={() => r.refetch()} />}
      {!r.data && !r.isError && <Loading />}
      {r.data && r.data.items.length === 0 && <EmptyState title="No accounts match" body="Try another search." />}
      {r.data && r.data.items.length > 0 && (
        <ul className="divide-y divide-line rounded-2xl border border-line bg-surface" aria-label="Accounts">
          {r.data.items.map((u) => (
            <li key={u._id} className="flex flex-wrap items-center gap-3 px-4 py-3">
              <div className="min-w-0 flex-1">
                <p className="flex flex-wrap items-center gap-2 font-medium">
                  {u.name ?? "(no name)"}
                  <Badge size="sm">{u.role}</Badge>
                  {u.demo && <Badge size="sm" variant="outline">Demo</Badge>}
                  {u.suspended && <Badge size="sm" variant="danger">Suspended</Badge>}
                </p>
                <p className="text-xs text-muted">
                  {u.email ?? "no email"} · <code>{u._id}</code>
                  {(u.creator_id || u.brand_id) && <> · {u.creator_id ?? u.brand_id}</>}
                </p>
                {u.suspended && u.suspended_reason && <p className="mt-0.5 text-xs text-fg-2">Reason: {u.suspended_reason}</p>}
              </div>
              {u.role !== "admin" &&
                (u.suspended ? (
                  <Button size="sm" variant="outline" onClick={() => setActing({ user: u, suspend: false })} aria-label={`Restore ${u.name ?? u._id}`}>
                    Restore
                  </Button>
                ) : (
                  <Button size="sm" variant="ghost" onClick={() => setActing({ user: u, suspend: true })} aria-label={`Suspend ${u.name ?? u._id}`}>
                    Suspend
                  </Button>
                ))}
            </li>
          ))}
        </ul>
      )}
      {acting && (
        <ReasonDialog
          title={`${acting.suspend ? "Suspend" : "Restore"} ${acting.user.name ?? acting.user._id}`}
          description={acting.suspend ? "They're signed out everywhere and can't sign in until restored." : "They can sign in again."}
          confirm={acting.suspend ? "Suspend account" : "Restore account"}
          danger={acting.suspend}
          onClose={() => setActing(null)}
          run={(reason) => adminApi(`/admin/accounts/${acting.user._id}/${acting.suspend ? "suspend" : "restore"}`, { reason })}
        />
      )}
    </div>
  );
}

// ------------------------------------------------------------------ campaigns
function CampaignsTab() {
  const [status, setStatus] = useState("");
  const [closing, setClosing] = useState<CampaignRow | null>(null);
  const r = useQuery({
    queryKey: ["admin", "campaigns", status],
    queryFn: () => adminApi<{ items: CampaignRow[] }>(`/admin/campaigns${status ? `?status=${status}` : ""}`),
    placeholderData: keepPreviousData,
  });
  return (
    <div className="space-y-4">
      <div className="max-w-xs">
        <Label htmlFor="camp-status">Status</Label>
        <Select id="camp-status" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All</option>
          <option value="draft">Draft</option>
          <option value="live">Live</option>
          <option value="paused">Paused</option>
          <option value="closed">Closed</option>
        </Select>
      </div>
      {r.isError && <ErrorState error={r.error} onRetry={() => r.refetch()} />}
      {!r.data && !r.isError && <Loading />}
      {r.data && r.data.items.length === 0 && <EmptyState title="No campaigns" body="Nothing with this status." />}
      {r.data && r.data.items.length > 0 && (
        <ul className="divide-y divide-line rounded-2xl border border-line bg-surface" aria-label="Campaigns">
          {r.data.items.map((c) => (
            <li key={c.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
              <div className="min-w-0 flex-1">
                <p className="flex flex-wrap items-center gap-2 font-medium">
                  {c.title} <Badge size="sm" variant={c.status === "live" ? "success" : "neutral"}>{c.status}</Badge>
                  {c.reports > 0 && <Badge size="sm" variant="warn">{c.reports} open report{c.reports === 1 ? "" : "s"}</Badge>}
                </p>
                <p className="text-xs text-muted">
                  {c.owner ?? c.owner_id} · <code>{c.id}</code>
                  {c.deadline && ` · until ${shortDate(c.deadline)}`}
                </p>
              </div>
              {c.status !== "closed" && (
                <Button size="sm" variant="ghost" onClick={() => setClosing(c)} aria-label={`Close ${c.title}`}>
                  Close
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
      {closing && (
        <ReasonDialog
          title={`Close “${closing.title}”`}
          description="Creators stop seeing it and it takes no more applications. Deals already made carry on."
          confirm="Close campaign"
          danger
          onClose={() => setClosing(null)}
          run={(reason) => adminApi(`/admin/campaigns/${closing.id}/close`, { reason })}
        />
      )}
    </div>
  );
}

// ------------------------------------------------------------------ reports
function ReportsTab() {
  const [status, setStatus] = useState<"open" | "resolved">("open");
  const [resolving, setResolving] = useState<Report | null>(null);
  const [resolution, setResolution] = useState("no_action");
  const r = useQuery({ queryKey: ["admin", "reports", status], queryFn: () => adminApi<{ items: Report[] }>(`/admin/reports?status=${status}`) });
  return (
    <div className="space-y-4">
      <div className="max-w-xs">
        <Label htmlFor="rep-status">Show</Label>
        <Select id="rep-status" value={status} onChange={(e) => setStatus(e.target.value as "open" | "resolved")}>
          <option value="open">Open</option>
          <option value="resolved">Resolved</option>
        </Select>
      </div>
      {r.isError && <ErrorState error={r.error} onRetry={() => r.refetch()} />}
      {!r.data && !r.isError && <Loading />}
      {r.data && r.data.items.length === 0 && <EmptyState title={status === "open" ? "No open reports" : "No resolved reports"} body="Reports from users show up here." />}
      {r.data && r.data.items.length > 0 && (
        <ul className="divide-y divide-line rounded-2xl border border-line bg-surface" aria-label="Reports">
          {r.data.items.map((x) => (
            <li key={x._id} className="flex flex-wrap items-start gap-3 px-4 py-3">
              <div className="min-w-0 flex-1">
                <p className="flex flex-wrap items-center gap-2 font-medium">
                  {REASON_LABEL[x.reason] ?? x.reason}
                  <Badge size="sm">
                    {x.target_type} <code className="ml-1">{x.target_id}</code>
                  </Badge>
                </p>
                {x.details && <p className="mt-1 text-sm text-fg-2">“{x.details}”</p>}
                <p className="mt-1 text-xs text-muted">
                  From a {x.reporter_role ?? "user"} account · {when(x.at)}
                </p>
                {x.resolution && (
                  <p className="mt-1 text-xs text-fg-2">
                    {x.resolution === "action_taken" ? "Action taken" : "No action"}: {x.resolution_reason}
                  </p>
                )}
              </div>
              {x.status === "open" && (
                <Button size="sm" variant="outline" onClick={() => (setResolution("no_action"), setResolving(x))}>
                  Resolve
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
      {resolving && (
        <ReasonDialog
          title="Resolve report"
          description="Suspend the account or close the campaign first if that's needed; this records the outcome."
          confirm="Resolve"
          onClose={() => setResolving(null)}
          run={(reason) => adminApi(`/admin/reports/${resolving._id}/resolve`, { resolution, reason })}
        >
          <div>
            <Label htmlFor="rep-resolution">Outcome</Label>
            <Select id="rep-resolution" value={resolution} onChange={(e) => setResolution(e.target.value)}>
              <option value="no_action">No action needed</option>
              <option value="action_taken">Action taken</option>
            </Select>
          </div>
        </ReasonDialog>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ brand pages
function BrandPagesTab() {
  const claims = useQuery({ queryKey: ["admin", "claims"], queryFn: () => adminApi<{ items: Claim[] }>("/admin/claims") });
  const removals = useQuery({ queryKey: ["admin", "removals"], queryFn: () => adminApi<{ items: Removal[] }>("/admin/removal-requests") });
  const [deciding, setDeciding] = useState<{ kind: "claim" | "removal"; id: string; name: string; yes: boolean } | null>(null);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ name: "", category: "", instagram: "", youtube: "" });
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Panel title="Claims waiting" icon={<Building2 className="size-4 text-accent" aria-hidden />}>
        {claims.isError && <ErrorState error={claims.error} onRetry={() => claims.refetch()} />}
        {claims.data && claims.data.items.length === 0 && <p className="text-sm text-muted">No claims waiting.</p>}
        <ul className="space-y-3">
          {claims.data?.items.map((c) => (
            <li key={c._id} className="rounded-xl border border-line p-3">
              <p className="font-medium">{c.brand_name}</p>
              <p className="text-xs text-muted">
                {c.user_name} · {c.user_email ?? "no email"} · {when(c.at)}
              </p>
              <p className="mt-1 text-sm text-fg-2">“{c.message}”</p>
              <div className="mt-2 flex gap-2">
                <Button size="sm" variant="primary" onClick={() => setDeciding({ kind: "claim", id: c._id, name: c.brand_name, yes: true })}>
                  Approve
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setDeciding({ kind: "claim", id: c._id, name: c.brand_name, yes: false })}>
                  Reject
                </Button>
              </div>
            </li>
          ))}
        </ul>
      </Panel>
      <Panel title="Removal requests" icon={<Flag className="size-4 text-accent" aria-hidden />}>
        {removals.isError && <ErrorState error={removals.error} onRetry={() => removals.refetch()} />}
        {removals.data && removals.data.items.length === 0 && <p className="text-sm text-muted">No removal requests waiting.</p>}
        <ul className="space-y-3">
          {removals.data?.items.map((r) => (
            <li key={r._id} className="rounded-xl border border-line p-3">
              <p className="font-medium">{r.brand_name}</p>
              <p className="text-xs text-muted">
                {r.contact ?? "no contact given"} · {when(r.at)}
              </p>
              <p className="mt-1 text-sm text-fg-2">“{r.reason}”</p>
              <div className="mt-2 flex gap-2">
                <Button size="sm" variant="danger" onClick={() => setDeciding({ kind: "removal", id: r._id, name: r.brand_name, yes: true })}>
                  Remove page
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setDeciding({ kind: "removal", id: r._id, name: r.brand_name, yes: false })}>
                  Keep page
                </Button>
              </div>
            </li>
          ))}
        </ul>
      </Panel>
      <Panel title="Add a brand that isn't on DealMeet AI" icon={<Building2 className="size-4 text-accent" aria-hidden />}>
        <p className="text-sm text-muted">Public name, category and public handles only. It's listed as unclaimed until the brand claims it.</p>
        <form
          className="mt-3 grid gap-3 sm:grid-cols-2"
          onSubmit={(e) => {
            e.preventDefault();
            setAdding(true);
          }}
        >
          <div>
            <Label htmlFor="ub-name">Brand name</Label>
            <Input id="ub-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} minLength={2} maxLength={60} required />
          </div>
          <div>
            <Label htmlFor="ub-cat">Category</Label>
            <Input id="ub-cat" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} minLength={2} maxLength={60} required />
          </div>
          <div>
            <Label htmlFor="ub-ig">Instagram handle (optional)</Label>
            <Input id="ub-ig" value={form.instagram} onChange={(e) => setForm({ ...form, instagram: e.target.value })} maxLength={41} placeholder="@brand" />
          </div>
          <div>
            <Label htmlFor="ub-yt">YouTube handle (optional)</Label>
            <Input id="ub-yt" value={form.youtube} onChange={(e) => setForm({ ...form, youtube: e.target.value })} maxLength={41} placeholder="@brand" />
          </div>
          <div className="sm:col-span-2">
            <Button type="submit" variant="outline" disabled={form.name.trim().length < 2 || form.category.trim().length < 2}>
              Add brand
            </Button>
          </div>
        </form>
      </Panel>
      <div className="lg:col-span-2">
        <ImportPanel />
      </div>
      <div className="lg:col-span-2">
        <InvitesPanel />
      </div>
      {adding && (
        <ReasonDialog
          title={`Add ${form.name}`}
          description="Listed as unclaimed, showing only public information, until the brand claims it."
          confirm="Add brand"
          onClose={() => setAdding(false)}
          run={async (reason) => {
            await adminApi("/admin/brands", {
              name: form.name,
              category: form.category,
              public_handles: { instagram: form.instagram || null, youtube: form.youtube || null },
              reason,
            });
            setForm({ name: "", category: "", instagram: "", youtube: "" });
          }}
        />
      )}
      {deciding && (
        <ReasonDialog
          title={
            deciding.kind === "claim" ? `${deciding.yes ? "Approve" : "Reject"} the claim on ${deciding.name}` : `${deciding.yes ? "Remove" : "Keep"} ${deciding.name}`
          }
          description={
            deciding.kind === "claim"
              ? deciding.yes
                ? "The account starts managing this brand page."
                : "The page stays unclaimed."
              : deciding.yes
                ? "The page disappears from the directory and creators' saved lists."
                : "The page stays listed."
          }
          confirm={deciding.kind === "claim" ? (deciding.yes ? "Approve" : "Reject") : deciding.yes ? "Remove page" : "Keep page"}
          danger={deciding.kind === "removal" && deciding.yes}
          onClose={() => setDeciding(null)}
          run={(reason) =>
            deciding.kind === "claim"
              ? adminApi(`/admin/claims/${deciding.id}`, { action: deciding.yes ? "approve" : "reject", reason })
              : adminApi(`/admin/removal-requests/${deciding.id}`, { action: deciding.yes ? "remove" : "keep", reason })
          }
        />
      )}
    </div>
  );
}

// ------------------------------------------------------------------ audit log
const SHOWN = new Set(["_id", "at", "ts", "action", "user_id", "role"]);

function AuditTab() {
  const [action, setAction] = useState("");
  const [userId, setUserId] = useState("");
  const [since, setSince] = useState("");
  const [until, setUntil] = useState("");
  const a = useDeferredValue(action.trim().toLowerCase().replace(/[^a-z_]/g, ""));
  const u = useDeferredValue(userId.trim());
  const params = new URLSearchParams({ limit: "200" });
  if (a) params.set("action", a);
  if (u) params.set("user_id", u);
  if (since) params.set("since", since);
  if (until) params.set("until", until);
  const r = useQuery({ queryKey: ["admin", "audit", params.toString()], queryFn: () => adminApi<{ items: AuditEvent[] }>(`/admin/audit?${params}`), placeholderData: keepPreviousData });
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-4">
        <div>
          <Label htmlFor="au-action">Action starts with</Label>
          <Input id="au-action" value={action} onChange={(e) => setAction(e.target.value)} placeholder="admin_" maxLength={60} />
        </div>
        <div>
          <Label htmlFor="au-user">Account id</Label>
          <Input id="au-user" value={userId} onChange={(e) => setUserId(e.target.value)} placeholder="us_…" maxLength={40} />
        </div>
        <div>
          <Label htmlFor="au-since">From</Label>
          <Input id="au-since" type="date" value={since} onChange={(e) => setSince(e.target.value)} />
        </div>
        <div>
          <Label htmlFor="au-until">To</Label>
          <Input id="au-until" type="date" value={until} onChange={(e) => setUntil(e.target.value)} />
        </div>
      </div>
      <p className="text-xs text-muted">Newest first, up to 200. Passwords, tokens and payment secrets are never logged, and anything that looks like one is hidden.</p>
      {r.isError && <ErrorState error={r.error} onRetry={() => r.refetch()} />}
      {!r.data && !r.isError && <Loading />}
      {r.data && r.data.items.length === 0 && <EmptyState title="Nothing logged" body="No events match these filters." />}
      {r.data && r.data.items.length > 0 && (
        <ol className="divide-y divide-line rounded-2xl border border-line bg-surface text-sm" aria-label="Audit events">
          {r.data.items.map((e) => {
            const rest = Object.entries(e).filter(([k]) => !SHOWN.has(k));
            return (
              <li key={e._id} className="px-4 py-2.5">
                <p className="flex flex-wrap items-center gap-2">
                  <code className="font-medium">{e.action}</code>
                  <span className="text-xs text-muted">{when(e.at)}</span>
                  {e.user_id && (
                    <span className="text-xs text-muted">
                      by <code>{e.user_id}</code> ({e.role ?? "?"})
                    </span>
                  )}
                </p>
                {rest.length > 0 && (
                  <p className="mt-0.5 break-words text-xs text-fg-2">
                    {rest.map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : String(v)}`).join(" · ")}
                  </p>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}


// ------------------------------------------------------------------ brand data: import and invites
const IMPORT_COLUMNS = "name,category,website,instagram,youtube,contact_email,city,source_url";
const IMPORT_EXAMPLE = `${IMPORT_COLUMNS}\nKumkum Tea,Beverages,https://kumkumtea.in,@kumkumtea,@KumkumTeaIN,partners@kumkumtea.in,Pune,https://kumkumtea.in/about\n`;

interface ImportRow {
  row: number;
  name: string | null;
  status: "ready" | "added" | "duplicate" | "removed" | "error";
  detail?: string;
  slug?: string;
}
interface ImportResult {
  dry_run: boolean;
  import_id: string | null;
  counts: Partial<Record<ImportRow["status"], number>>;
  rows: ImportRow[];
}

const STATUS_LABEL: Record<ImportRow["status"], string> = { ready: "Ready", added: "Added", duplicate: "Already listed", removed: "Removed earlier", error: "Fix this row" };
const STATUS_TONE: Record<ImportRow["status"], "success" | "neutral" | "warn" | "danger"> = { ready: "success", added: "success", duplicate: "neutral", removed: "warn", error: "danger" };

/** Many unclaimed brands at once, from public facts: checked first, saved only on confirm. */
function ImportPanel() {
  const [text, setText] = useState("");
  const [result, setResult] = useState<ImportResult | null>(null);
  const [confirming, setConfirming] = useState(false);
  const check = useMutation({
    mutationFn: () => adminApi<ImportResult>("/admin/brands/import", { csv: text, dry_run: true }),
    onSuccess: setResult,
    onError: (e) => toast.error((e as Error).message),
  });
  const ready = result?.dry_run ? (result.counts.ready ?? 0) : 0;
  return (
    <Panel title="Import brands from a CSV" icon={<FileUp className="size-4 text-accent" aria-hidden />}>
      <p className="text-sm text-muted">
        Public facts only, each row with the page it came from (source_url). Pages show name, category and handles; the website, city and contact address stay
        private. A contact email must be at the brand's own website domain. Up to 500 rows; nothing is saved until you confirm.
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-sm hover:bg-surface-2">
          <FileUp className="size-4" aria-hidden /> Choose a .csv file
          <input
            type="file"
            accept=".csv,text/csv"
            className="sr-only"
            onChange={async (e) => {
              const f = e.target.files?.[0];
              if (f) {
                setText(await f.text());
                setResult(null);
              }
            }}
          />
        </label>
        <a
          href={`data:text/csv;charset=utf-8,${encodeURIComponent(IMPORT_EXAMPLE)}`}
          download="brands-template.csv"
          className="text-sm font-medium text-accent hover:underline"
        >
          Download the template
        </a>
      </div>
      <Label htmlFor="import-csv" className="mt-3 block">
        Or paste the CSV
      </Label>
      <Textarea
        id="import-csv"
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          setResult(null);
        }}
        className="min-h-32 font-mono text-xs"
        placeholder={IMPORT_COLUMNS}
        spellCheck={false}
      />
      <div className="mt-3 flex flex-wrap gap-2">
        <Button variant="outline" onClick={() => check.mutate()} loading={check.isPending} disabled={!text.trim()}>
          Check file
        </Button>
        {result?.dry_run && ready > 0 && (
          <Button variant="primary" onClick={() => setConfirming(true)}>
            Import {ready} brand{ready === 1 ? "" : "s"}
          </Button>
        )}
      </div>
      {result && (
        <div className="mt-4">
          <p className="flex flex-wrap gap-2 text-sm" aria-live="polite">
            {(Object.keys(result.counts) as ImportRow["status"][]).map((k) => (
              <Badge key={k} size="sm" variant={STATUS_TONE[k]}>
                {result.counts[k]} {STATUS_LABEL[k].toLowerCase()}
              </Badge>
            ))}
          </p>
          <div className="mt-2 max-h-80 overflow-auto rounded-xl border border-line">
            <table className="w-full text-left text-[13px]">
              <thead className="sticky top-0 bg-surface-2 text-xs text-muted">
                <tr>
                  <th scope="col" className="px-3 py-2 font-medium">Row</th>
                  <th scope="col" className="px-3 py-2 font-medium">Brand</th>
                  <th scope="col" className="px-3 py-2 font-medium">Result</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {result.rows.map((r) => (
                  <tr key={r.row}>
                    <td className="num px-3 py-2 text-muted">{r.row}</td>
                    <td className="px-3 py-2">{r.slug ? <Link to={`/brands/${r.slug}`} className="text-accent hover:underline">{r.name}</Link> : (r.name ?? "—")}</td>
                    <td className="px-3 py-2">
                      <Badge size="sm" variant={STATUS_TONE[r.status]}>
                        {STATUS_LABEL[r.status]}
                      </Badge>
                      {r.detail && <span className="ml-2 text-xs text-fg-2">{r.detail}</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      {confirming && (
        <ReasonDialog
          title={`Import ${ready} brand${ready === 1 ? "" : "s"}`}
          description="They're listed as unclaimed, with public basics only, until each brand claims its page. Rows with problems or duplicates are skipped."
          confirm="Import"
          onClose={() => setConfirming(false)}
          run={async (reason) => setResult(await adminApi<ImportResult>("/admin/brands/import", { csv: text, dry_run: false, reason }))}
        />
      )}
    </Panel>
  );
}

interface InviteRow {
  id: string;
  name: string;
  slug: string;
  saves: number;
  contact_email: string | null;
  last_invite: string | null;
  blocked: string | null;
}

/** Unclaimed brands creators want: tell them once, by email, with a claim link. */
function InvitesPanel() {
  const q = useQuery({ queryKey: ["admin", "brand-invites"], queryFn: () => adminApi<{ items: InviteRow[]; min_saves: number; email: boolean }>("/admin/brand-invites") });
  const [inviting, setInviting] = useState<InviteRow | null>(null);
  return (
    <Panel title="Invite brands creators want" icon={<Mail className="size-4 text-accent" aria-hidden />}>
      <p className="text-sm text-muted">
        Unclaimed brands saved by creators with connected accounts. An invite tells the brand's public contact address how many want to work with them, with a
        claim link and an unsubscribe link. At most once every 30 days per brand.
      </p>
      {q.data && !q.data.email && (
        <p role="note" className="mt-3 rounded-xl border border-warn/40 bg-warn-soft p-3 text-sm">
          Email isn't set up on this server (SMTP_HOST and EMAIL_FROM), so invites can't be sent yet.
        </p>
      )}
      {q.isError && <ErrorState error={q.error} onRetry={() => q.refetch()} />}
      {q.data && q.data.items.length === 0 && (
        <p className="mt-3 text-sm text-muted">No unclaimed brand has {q.data.min_saves} or more saves from creators with connected accounts yet.</p>
      )}
      <ul className="mt-3 space-y-2">
        {q.data?.items.map((b) => (
          <li key={b.id} className="flex flex-wrap items-center gap-3 rounded-xl border border-line p-3">
            <div className="min-w-0 flex-1">
              <Link to={`/brands/${b.slug}`} className="font-medium hover:text-accent">
                {b.name}
              </Link>
              <p className="text-xs text-muted">
                <span className="num">{b.saves}</span> saves · {b.contact_email ?? "no public contact address"}
                {b.last_invite && ` · invited ${when(b.last_invite)}`}
              </p>
              {b.blocked && <p className="mt-0.5 text-xs text-fg-2">{b.blocked}</p>}
            </div>
            <Button size="sm" variant="outline" disabled={!!b.blocked || !q.data?.email} onClick={() => setInviting(b)}>
              <Mail aria-hidden /> Send invite
            </Button>
          </li>
        ))}
      </ul>
      {inviting && (
        <ReasonDialog
          title={`Invite ${inviting.name}`}
          description={`Emails ${inviting.contact_email}: ${inviting.saves} creators with connected accounts saved them, with a link to claim the page.`}
          confirm="Send invite"
          onClose={() => setInviting(null)}
          run={(reason) => adminApi(`/admin/brand-invites/${inviting.id}`, { reason })}
        />
      )}
    </Panel>
  );
}
