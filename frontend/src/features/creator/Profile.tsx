import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, CircleDashed, Link2, MinusCircle, Save, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { ErrorState, ScoreRing } from "@/components/shared/Bits";
import { SourceBadge } from "@/components/shared/SourceBadge";
import { Button } from "@/components/ui/button";
import { ChipGroup, FieldHint, Input, Label, Segmented, Select, Skeleton, Textarea } from "@/components/ui/form";
import { api } from "@/lib/api";
import { count, shortDate } from "@/lib/format";
import { useCreatorId } from "@/lib/session";
import type { Creator } from "@/lib/types";
import type { PlatformStatus } from "@/lib/youtube-types";
import { StatusChip } from "./Connections";

interface CheckItem {
  key: string;
  label: string;
  done: boolean;
  fix: string | null;
}

interface ReadyItem {
  key: string;
  label: string;
  status: "passed" | "failed" | "connect" | "not_applicable";
  detail: string;
  source: string | null;
}

interface Manual {
  id: string;
  platform: string;
  followers: number;
  avg_views: number | null;
  engagement_pct: number | null;
  source: "manual";
  at: string;
}

interface ProfileData {
  creator: Creator & { sub_niches?: string[]; formats?: string[]; platforms?: string[]; sources?: Record<string, string> };
  collab_prefs: { accepts: "paid" | "barter" | "both" | null; min_fee: number | null; avoid: string[] };
  manual: Manual | null;
  manual_history: Manual[];
  platforms: PlatformStatus[];
  completeness: { score: number; done: number; total: number; items: CheckItem[]; method: string };
  readiness: { score: number; passed: number; applicable: number; to_connect: number; items: ReadyItem[]; method: string };
  note?: string | null;
}

interface Meta {
  niches: { id: string; label: string }[];
  languages: { id: string; label: string }[];
  formats: { id: string; label: string }[];
  cities: { name: string }[];
}

export default function Profile() {
  const id = useCreatorId();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["profile", id], queryFn: () => api<ProfileData>(`/creators/${id}/profile`) });
  const meta = useQuery({ queryKey: ["meta"], queryFn: () => api<Meta>("/meta") });
  const onSaved = (d: ProfileData) => {
    qc.setQueryData(["profile", id], d);
    void qc.invalidateQueries({ predicate: (x) => x.queryKey[0] !== "profile" });
  };
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data || !meta.data) return <Skeleton className="h-96 rounded-[var(--radius-card)]" />;
  const d = q.data;

  return (
    <div>
      <h1 className="font-display text-[26px] font-semibold tracking-tight sm:text-[30px]">Your profile</h1>
      <p className="mt-1 max-w-2xl text-[15px] text-fg-2">What brands see about you, and how ready it is for them. Your email, phone and earnings are never shown to brands.</p>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <section aria-labelledby="complete" className="card-surface rounded-[var(--radius-card)] p-5">
          <div className="flex items-center gap-4">
            <ScoreRing value={d.completeness.score} size={96} stroke={8} sublabel="of 100" />
            <div>
              <h2 id="complete" className="font-display text-lg font-semibold">
                Profile completeness
              </h2>
              <p className="text-xs text-muted">{d.completeness.method}</p>
            </div>
          </div>
          <ul className="mt-4 space-y-2">
            {d.completeness.items.map((i) => (
              <li key={i.key} className="flex gap-2.5 text-[13px]">
                {i.done ? <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-success" aria-hidden /> : <CircleDashed className="mt-0.5 size-4 shrink-0 text-muted" aria-hidden />}
                <span>
                  <span className={i.done ? "text-fg-2" : "font-medium"}>{i.label}</span>
                  <span className="sr-only">{i.done ? ": done" : ": missing"}</span>
                  {i.fix && <span className="block text-xs text-muted">{i.fix}</span>}
                </span>
              </li>
            ))}
          </ul>
        </section>

        <section aria-labelledby="ready" className="card-surface rounded-[var(--radius-card)] p-5">
          <div className="flex items-center gap-4">
            <ScoreRing value={d.readiness.score} size={96} stroke={8} sublabel="of 100" />
            <div>
              <h2 id="ready" className="font-display text-lg font-semibold">
                Brand-readiness
              </h2>
              <p className="text-xs text-muted">
                {d.readiness.passed} of {d.readiness.applicable} ready
                {d.readiness.to_connect > 0 && ` · ${d.readiness.to_connect} need a connected account`}
              </p>
            </div>
          </div>
          <ul className="mt-4 space-y-2">
            {d.readiness.items.map((i) => (
              <li key={i.key} className="flex gap-2.5 text-[13px]">
                <ReadyIcon status={i.status} />
                <span className="min-w-0 flex-1">
                  <span className="flex flex-wrap items-center gap-1.5 font-medium">
                    {i.label}
                    <span className="font-normal text-muted">· {READY_LABEL[i.status]}</span>
                    {i.source && i.status !== "connect" && <SourceBadge source={i.source} />}
                  </span>
                  <span className="block text-xs text-muted">{i.detail}</span>
                </span>
              </li>
            ))}
          </ul>
          {d.readiness.to_connect > 0 && (
            <Button asChild size="sm" variant="outline" className="mt-4">
              <Link to="/creator/connections">
                <Link2 aria-hidden /> Connect an account
              </Link>
            </Button>
          )}
        </section>
      </div>

      <section aria-labelledby="platforms" className="mt-4 flex flex-wrap items-center gap-3 rounded-[var(--radius-card)] border border-line bg-surface p-4">
        <h2 id="platforms" className="text-sm font-semibold">
          Platforms
        </h2>
        {d.platforms.map((p) => (
          <span key={p.platform} className="inline-flex items-center gap-1.5 text-sm">
            {p.label} <StatusChip status={p.status} />
          </span>
        ))}
        <Link to="/creator/connections" className="ml-auto text-sm text-accent hover:underline">
          Manage connections
        </Link>
      </section>

      <EditForm data={d} meta={meta.data} creatorId={id} onSaved={onSaved} />
      <ManualForm data={d} creatorId={id} onSaved={onSaved} />
    </div>
  );
}

const READY_LABEL: Record<ReadyItem["status"], string> = { passed: "ready", failed: "not yet", connect: "connect to check", not_applicable: "nothing to check yet" };

function ReadyIcon({ status }: { status: ReadyItem["status"] }) {
  if (status === "passed") return <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-success" aria-hidden />;
  if (status === "failed") return <XCircle className="mt-0.5 size-4 shrink-0 text-warn" aria-hidden />;
  if (status === "not_applicable") return <MinusCircle className="mt-0.5 size-4 shrink-0 text-muted" aria-hidden />;
  return <CircleDashed className="mt-0.5 size-4 shrink-0 text-muted" aria-hidden />;
}

function EditForm({ data, meta, creatorId, onSaved }: { data: ProfileData; meta: Meta; creatorId: string; onSaved: (d: ProfileData) => void }) {
  const c = data.creator;
  const [f, setF] = useState(() => ({
    name: c.name,
    bio: c.bio ?? "",
    niche: c.niche,
    categories: (c.sub_niches ?? []).join(", "),
    city: c.city ?? "",
    languages: c.languages,
    formats: c.formats ?? [],
    platforms: c.platforms ?? [],
    accepts: data.collab_prefs.accepts ?? "both",
    min_fee: data.collab_prefs.min_fee != null ? String(data.collab_prefs.min_fee) : "",
    avoid: (data.collab_prefs.avoid ?? []).join(", "),
  }));
  useEffect(() => setF((p) => ({ ...p, name: c.name })), [c.name]);
  const set = <K extends keyof typeof f>(k: K, v: (typeof f)[K]) => setF((p) => ({ ...p, [k]: v }));
  const save = useMutation({
    mutationFn: () =>
      api<ProfileData>(`/creators/${creatorId}/profile`, {
        method: "PATCH",
        json: {
          name: f.name,
          bio: f.bio,
          niche: f.niche,
          sub_niches: split(f.categories),
          city: f.city || undefined,
          languages: f.languages,
          formats: f.formats,
          platforms: f.platforms,
          collab_prefs: { accepts: f.accepts, min_fee: f.min_fee ? Number(f.min_fee.replace(/[^\d]/g, "")) : null, avoid: split(f.avoid) },
        },
      }),
    onSuccess: (d) => {
      onSaved(d);
      toast.success("Profile saved");
    },
    onError: (e) => toast.error((e as Error).message),
  });

  return (
    <section aria-labelledby="edit" className="card-surface mt-4 rounded-[var(--radius-card)] p-5">
      <h2 id="edit" className="font-display text-lg font-semibold">
        Edit profile
      </h2>
      <form
        className="mt-4 grid gap-4 md:grid-cols-2"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <div>
          <Label htmlFor="pf-name">Name</Label>
          <Input id="pf-name" value={f.name} onChange={(e) => set("name", e.target.value)} required maxLength={60} />
        </div>
        <div>
          <Label htmlFor="pf-niche">Main niche</Label>
          <Select id="pf-niche" value={f.niche} onChange={(e) => set("niche", e.target.value)}>
            {meta.niches.map((n) => (
              <option key={n.id} value={n.id}>
                {n.label}
              </option>
            ))}
          </Select>
        </div>
        <div className="md:col-span-2">
          <Label htmlFor="pf-bio">Bio</Label>
          <Textarea id="pf-bio" value={f.bio} onChange={(e) => set("bio", e.target.value)} maxLength={400} className="min-h-20" />
          <FieldHint>{f.bio.trim().length}/400. Two lines on what you make and who watches it.</FieldHint>
        </div>
        <div>
          <Label htmlFor="pf-cats">Content categories</Label>
          <Input id="pf-cats" value={f.categories} onChange={(e) => set("categories", e.target.value)} placeholder="quick breakfasts, festive sweets" />
          <FieldHint>Up to six, separated by commas.</FieldHint>
        </div>
        <div>
          <Label htmlFor="pf-city">City</Label>
          <Select id="pf-city" value={f.city} onChange={(e) => set("city", e.target.value)}>
            <option value="">Choose a city</option>
            {meta.cities.map((x) => (
              <option key={x.name} value={x.name}>
                {x.name}
              </option>
            ))}
          </Select>
        </div>
        <div className="md:col-span-2">
          <p className="mb-2 text-[13px] font-medium text-fg-2">Languages you post in</p>
          <ChipGroup label="Languages" values={f.languages} onChange={(v) => set("languages", v)} options={meta.languages.map((l) => ({ value: l.id, label: l.label }))} />
        </div>
        <div>
          <p className="mb-2 text-[13px] font-medium text-fg-2">Formats</p>
          <ChipGroup label="Formats" values={f.formats} onChange={(v) => set("formats", v)} options={meta.formats.map((x) => ({ value: x.id, label: x.label }))} />
        </div>
        <div>
          <p className="mb-2 text-[13px] font-medium text-fg-2">Platforms</p>
          <ChipGroup
            label="Platforms"
            values={f.platforms}
            onChange={(v) => set("platforms", v)}
            options={[
              { value: "instagram", label: "Instagram" },
              { value: "youtube", label: "YouTube" },
            ]}
          />
        </div>
        <fieldset className="md:col-span-2 rounded-2xl border border-line p-4">
          <legend className="px-1 text-[13px] font-medium text-fg-2">Collaboration preferences</legend>
          <div className="grid gap-4 md:grid-cols-3">
            <div>
              <p className="mb-2 text-xs text-muted">Deals you take</p>
              <Segmented
                label="Deals you take"
                value={f.accepts}
                onChange={(v) => set("accepts", v)}
                size="sm"
                options={[
                  { value: "paid", label: "Paid" },
                  { value: "barter", label: "Barter" },
                  { value: "both", label: "Both" },
                ]}
              />
            </div>
            <div>
              <Label htmlFor="pf-min">Minimum fee (₹)</Label>
              <Input id="pf-min" inputMode="numeric" value={f.min_fee} onChange={(e) => set("min_fee", e.target.value)} placeholder="3000" />
            </div>
            <div>
              <Label htmlFor="pf-avoid">Categories to avoid</Label>
              <Input id="pf-avoid" value={f.avoid} onChange={(e) => set("avoid", e.target.value)} placeholder="alcohol, betting" />
            </div>
          </div>
          <FieldHint className="mt-2">Opportunities that don't fit these are hidden from your list, with the reason.</FieldHint>
        </fieldset>
        <div className="md:col-span-2 flex justify-end">
          <Button type="submit" variant="primary" loading={save.isPending}>
            {!save.isPending && <Save aria-hidden />} Save profile
          </Button>
        </div>
      </form>
    </section>
  );
}

function split(s: string) {
  return s
    .split(",")
    .map((x) => x.trim())
    .filter(Boolean);
}

function ManualForm({ data, creatorId, onSaved }: { data: ProfileData; creatorId: string; onSaved: (d: ProfileData) => void }) {
  const [platform, setPlatform] = useState<"instagram" | "youtube">("instagram");
  const [followers, setFollowers] = useState("");
  const [views, setViews] = useState("");
  const [eng, setEng] = useState("");
  const num = (s: string) => Number(s.replace(/[^\d.]/g, ""));
  const add = useMutation({
    mutationFn: () =>
      api<ProfileData & { note: string | null; applied: boolean }>(`/creators/${creatorId}/manual-metrics`, {
        method: "POST",
        json: { platform, followers: num(followers), avg_views: views ? num(views) : null, engagement_pct: eng ? num(eng) : null },
      }),
    onSuccess: (d) => {
      onSaved(d);
      setFollowers("");
      setViews("");
      setEng("");
      if (d.note) toast.info(d.note);
      else toast.success("Saved", { description: "Labelled Self-reported wherever it's shown." });
    },
    onError: (e) => toast.error((e as Error).message),
  });

  return (
    <section aria-labelledby="manual" className="card-surface mt-4 rounded-[var(--radius-card)] p-5">
      <h2 id="manual" className="flex flex-wrap items-center gap-2 font-display text-lg font-semibold">
        Self-reported numbers <SourceBadge source="manual" />
      </h2>
      <p className="mt-1 text-sm text-fg-2">
        No connected account yet? Type your numbers. They're labelled Self-reported, kept with their history, and never replace numbers from a connected account.
      </p>
      <form
        className="mt-4 grid items-end gap-3 sm:grid-cols-[150px_1fr_1fr_1fr_auto]"
        onSubmit={(e) => {
          e.preventDefault();
          add.mutate();
        }}
      >
        <div>
          <Label htmlFor="mm-platform">Platform</Label>
          <Select id="mm-platform" value={platform} onChange={(e) => setPlatform(e.target.value as "instagram" | "youtube")}>
            <option value="instagram">Instagram</option>
            <option value="youtube">YouTube</option>
          </Select>
        </div>
        <div>
          <Label htmlFor="mm-followers">Followers</Label>
          <Input id="mm-followers" inputMode="numeric" value={followers} onChange={(e) => setFollowers(e.target.value)} required />
        </div>
        <div>
          <Label htmlFor="mm-views">Average views</Label>
          <Input id="mm-views" inputMode="numeric" value={views} onChange={(e) => setViews(e.target.value)} />
        </div>
        <div>
          <Label htmlFor="mm-eng">Engagement %</Label>
          <Input id="mm-eng" inputMode="decimal" value={eng} onChange={(e) => setEng(e.target.value)} />
        </div>
        <Button type="submit" variant="outline" loading={add.isPending}>
          Save numbers
        </Button>
      </form>
      {data.manual_history.length > 0 && (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[480px] text-left text-[13px]">
            <caption className="sr-only">Self-reported numbers you've entered</caption>
            <thead className="text-xs text-muted">
              <tr>
                <th scope="col" className="py-1.5 font-medium">Date</th>
                <th scope="col" className="py-1.5 font-medium">Platform</th>
                <th scope="col" className="py-1.5 text-right font-medium">Followers</th>
                <th scope="col" className="py-1.5 text-right font-medium">Avg views</th>
                <th scope="col" className="py-1.5 text-right font-medium">Engagement</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {data.manual_history.map((m) => (
                <tr key={m.id}>
                  <td className="py-2">{shortDate(m.at)}</td>
                  <td className="py-2 capitalize">{m.platform}</td>
                  <td className="num py-2 text-right">{count(m.followers)}</td>
                  <td className="num py-2 text-right">{m.avg_views != null ? count(m.avg_views) : "–"}</td>
                  <td className="num py-2 text-right">{m.engagement_pct != null ? `${m.engagement_pct}%` : "–"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
