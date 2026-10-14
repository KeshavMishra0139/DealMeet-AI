import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CityOptions } from "@/components/shared/CityOptions";
import { AlertCircle, ArrowLeft, Minus, Plus, Users } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { ErrorState } from "@/components/shared/Bits";
import { Button } from "@/components/ui/button";
import { ChipGroup, FieldHint, Input, Label, Segmented, Select, Skeleton, Switch, Textarea } from "@/components/ui/form";
import { api, ApiError, post, type MissingItem } from "@/lib/api";
import type { Listing } from "@/lib/market-types";
import { useBrandId } from "@/lib/session";
import { useBrand } from "./BrandShell";

interface Meta {
  niches: { id: string; label: string }[];
  languages: { id: string; label: string; native: string }[];
  cities: { name: string; state: string; region: string }[];
}

const REGIONS = ["North", "South", "East", "West", "Central", "Northeast"];
const AGES = ["13-17", "18-24", "25-34", "35-44", "45+"];
const OBJECTIVES = [
  { value: "awareness", label: "Awareness" },
  { value: "consideration", label: "Consideration" },
  { value: "sales", label: "Sales" },
  { value: "launch", label: "Product launch" },
  { value: "content", label: "Content for ads" },
];

function Stepper({ label, value, onChange, min = 0, max = 10 }: { label: string; value: number; onChange: (v: number) => void; min?: number; max?: number }) {
  return (
    <div>
      <p className="mb-1.5 text-[13px] font-medium text-fg-2">{label}</p>
      <div className="inline-flex items-center rounded-xl border border-line-strong">
        <Button type="button" variant="ghost" size="icon-sm" aria-label={`Fewer ${label.toLowerCase()}`} onClick={() => onChange(Math.max(min, value - 1))}>
          <Minus />
        </Button>
        <span className="num w-8 text-center text-sm font-semibold" aria-live="polite">
          {value}
        </span>
        <Button type="button" variant="ghost" size="icon-sm" aria-label={`More ${label.toLowerCase()}`} onClick={() => onChange(Math.min(max, value + 1))}>
          <Plus />
        </Button>
      </div>
    </div>
  );
}

const EMPTY = {
  title: "",
  summary: "",
  objectives: [] as string[],
  niches: [] as string[],
  languages: [] as string[],
  ages: [] as string[],
  gender: "any" as "any" | "female" | "male",
  scope: "pan" as "pan" | "regions",
  regions: [] as string[],
  cities: [] as string[],
  collective: false,
  collective_size: 20,
  budget_min: "5000",
  budget_max: "20000",
  budget_total: "100000",
  reels: 1,
  stories: 2,
  usage: "30",
  exclusivity: "0",
  start_date: "",
  deadline: "",
};
type Form = typeof EMPTY;

function fromListing(l: Listing): Form {
  const count = (k: string) => l.deliverables.find((d) => d.kind === k)?.count ?? 0;
  const pan = l.regions.includes("Pan-India") || l.regions.length === 0;
  return {
    title: l.title,
    summary: l.summary,
    objectives: l.objectives ?? [],
    niches: l.niches,
    languages: l.languages,
    ages: l.audience?.ages ?? [],
    gender: l.audience?.gender ?? "any",
    scope: pan ? "pan" : "regions",
    regions: pan ? [] : l.regions,
    cities: l.cities ?? [],
    collective: l.type === "collective",
    collective_size: l.collective_size ?? 20,
    budget_min: String(l.budget.per_creator_min ?? ""),
    budget_max: String(l.budget.per_creator_max ?? ""),
    budget_total: String(l.budget.total ?? ""),
    reels: count("reel"),
    stories: count("story"),
    usage: String(l.usage_rights_days),
    exclusivity: String(l.exclusivity_days),
    start_date: l.start_date ?? "",
    deadline: l.deadline ?? "",
  };
}

/** New campaign, or editing one (/brand/campaigns/:id/edit). New campaigns start as drafts. */
export default function NewCampaign() {
  const { id: editId } = useParams();
  const brandId = useBrandId();
  const brand = useBrand();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const meta = useQuery({ queryKey: ["meta"], queryFn: () => api<Meta>("/meta") });
  const existing = useQuery({ queryKey: ["listing", editId], queryFn: () => api<Listing>(`/listings/${editId}`), enabled: !!editId });
  const [f, setF] = useState<Form>(EMPTY);
  const [loaded, setLoaded] = useState(!editId);
  const [problems, setProblems] = useState<MissingItem[]>([]);
  const set = <K extends keyof Form>(k: K, v: Form[K]) => setF((p) => ({ ...p, [k]: v }));
  const num = (s: string) => Number(s.replace(/[^\d]/g, "")) || 0;

  useEffect(() => {
    if (existing.data && !loaded) {
      setF(fromListing(existing.data));
      setLoaded(true);
    }
  }, [existing.data, loaded]);

  const body = () => ({
    title: f.title,
    summary: f.summary,
    objectives: f.objectives,
    niches: f.niches,
    languages: f.languages,
    audience_ages: f.ages,
    audience_gender: f.gender,
    regions: f.scope === "pan" ? ["Pan-India"] : f.regions,
    cities: f.cities,
    collective_size: f.collective_size,
    ...(f.collective ? { budget_total: num(f.budget_total) } : { budget_min: num(f.budget_min), budget_max: num(f.budget_max) }),
    reels: f.reels,
    stories: f.stories,
    usage_rights_days: num(f.usage),
    exclusivity_days: num(f.exclusivity),
    start_date: f.start_date || null,
    deadline: f.deadline || null,
  });

  const fail = (e: unknown) => {
    setProblems(e instanceof ApiError ? e.missing : []);
    toast.error((e as Error).message);
  };
  const create = useMutation({
    mutationFn: async (publish: boolean) => {
      const made = await post<{ id: string }>(`/brands/${brandId}/campaigns`, { ...body(), collective: f.collective });
      if (!publish) return { id: made.id, published: false, problem: null };
      try {
        await post(`/campaigns/${made.id}/status`, { action: "publish" });
        return { id: made.id, published: true, problem: null };
      } catch (e) {
        return { id: made.id, published: false, problem: e as Error };
      }
    },
    onSuccess: ({ id, published, problem }) => {
      void qc.invalidateQueries({ queryKey: ["console", brandId] });
      if (problem) toast(`Saved as a draft`, { description: `${problem.message} The checklist shows what to add.` });
      else toast.success(published ? "Campaign live" : "Draft saved", { description: published ? "Matching creators can see it and apply." : "Creators can't see it until you publish." });
      navigate(`/brand/campaigns/${id}`);
    },
    onError: fail,
  });
  const save = useMutation({
    mutationFn: () => api<Listing>(`/campaigns/${editId}`, { method: "PATCH", json: body() }),
    onSuccess: (l) => {
      qc.setQueryData(["listing", editId], l);
      void qc.invalidateQueries({ queryKey: ["console", brandId] });
      toast.success("Changes saved");
      navigate(`/brand/campaigns/${editId}`);
    },
    onError: fail,
  });

  if (editId && existing.isError) return <ErrorState error={existing.error} onRetry={() => existing.refetch()} />;
  if (!loaded) return <Skeleton className="h-96 rounded-xl" />;
  const status = existing.data?.status;
  const valid = f.title.trim().length >= 4;
  const busy = create.isPending || save.isPending;

  return (
    <div className="max-w-3xl">
      <Link to={editId ? `/brand/campaigns/${editId}` : "/brand/campaigns"} className="inline-flex items-center gap-1 text-xs font-medium text-muted hover:text-fg">
        <ArrowLeft className="size-3.5" aria-hidden /> {editId ? "Back to the campaign" : "Campaigns"}
      </Link>
      <h1 className="mt-2 font-display text-2xl font-semibold tracking-tight">{editId ? "Edit campaign" : "New campaign"}</h1>
      <p className="mt-1 text-sm text-fg-2">
        {editId && status && status !== "draft"
          ? "This campaign is " + status + ". Changes that would leave it incomplete aren't saved."
          : `Describe the brief. We rank creators who fit ${brand.data ? brand.data.name : "your brand"}'s audience and price each match fairly. It stays a draft, hidden from creators, until you publish.`}
      </p>

      <form
        className="mt-6 space-y-5"
        onSubmit={(e) => {
          e.preventDefault();
          if (editId) save.mutate();
          else create.mutate(true);
        }}
      >
        <section className="card-surface space-y-4 rounded-xl p-5" aria-label="About the campaign">
          <div>
            <Label htmlFor="nc-title">Title</Label>
            <Input id="nc-title" value={f.title} onChange={(e) => set("title", e.target.value)} placeholder="For example, Winter drop: anime hoodies" maxLength={90} />
          </div>
          <div>
            <Label htmlFor="nc-sum">Brief</Label>
            <Textarea id="nc-sum" value={f.summary} onChange={(e) => set("summary", e.target.value)} maxLength={400} placeholder="What creators should make, and what a great post looks like" />
          </div>
          <div>
            <p className="mb-2 text-[13px] font-medium text-fg-2">Objectives</p>
            <ChipGroup label="Objectives" values={f.objectives} onChange={(v) => set("objectives", v)} options={OBJECTIVES} />
          </div>
          <div>
            <p className="mb-2 text-[13px] font-medium text-fg-2">Creator niches</p>
            {meta.data && <ChipGroup label="Niches" values={f.niches} onChange={(v) => set("niches", v)} options={meta.data.niches.map((n) => ({ value: n.id, label: n.label }))} />}
          </div>
          <div>
            <p className="mb-2 text-[13px] font-medium text-fg-2">Languages</p>
            {meta.data && (
              <ChipGroup label="Languages" values={f.languages} onChange={(v) => set("languages", v)} options={meta.data.languages.map((l) => ({ value: l.id, label: l.label }))} />
            )}
          </div>
        </section>

        <section className="card-surface space-y-4 rounded-xl p-5" aria-label="Audience and geography">
          <div>
            <p className="mb-2 text-[13px] font-medium text-fg-2">Target audience ages</p>
            <ChipGroup label="Audience ages" values={f.ages} onChange={(v) => set("ages", v)} options={AGES.map((a) => ({ value: a, label: a }))} />
          </div>
          <div>
            <p className="mb-2 text-[13px] font-medium text-fg-2">Audience</p>
            <Segmented
              label="Audience gender"
              value={f.gender}
              onChange={(v) => set("gender", v)}
              options={[
                { value: "any", label: "Everyone" },
                { value: "female", label: "Mostly women" },
                { value: "male", label: "Mostly men" },
              ]}
            />
          </div>
          <div>
            <p className="mb-2 text-[13px] font-medium text-fg-2">Where</p>
            <Segmented
              label="Region scope"
              value={f.scope}
              onChange={(v) => set("scope", v)}
              options={[
                { value: "pan", label: "Pan-India" },
                { value: "regions", label: "Specific regions" },
              ]}
            />
            {f.scope === "regions" && (
              <div className="mt-3">
                <ChipGroup label="Regions" values={f.regions} onChange={(v) => set("regions", v)} options={REGIONS.map((r) => ({ value: r, label: r }))} />
              </div>
            )}
          </div>
          <div>
            <Label htmlFor="nc-city">Priority cities (optional)</Label>
            <Select
              id="nc-city"
              value=""
              onChange={(e) => e.target.value && !f.cities.includes(e.target.value) && set("cities", [...f.cities, e.target.value])}
              className="h-10 text-sm"
            >
              <option value="">Add a city</option>
              {meta.data && <CityOptions cities={meta.data.cities} />}
            </Select>
            {f.cities.length > 0 && (
              <ul className="mt-2 flex flex-wrap gap-1.5" aria-label="Priority cities">
                {f.cities.map((c) => (
                  <li key={c}>
                    <button type="button" onClick={() => set("cities", f.cities.filter((x) => x !== c))} className="rounded-full border border-line px-2.5 py-1 text-xs hover:border-danger/60" aria-label={`Remove ${c}`}>
                      {c} ×
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>

        <section className="card-surface space-y-4 rounded-xl p-5" aria-label="Deliverables and usage">
          <div className="flex flex-wrap gap-6">
            <Stepper label="Reels" value={f.reels} onChange={(v) => set("reels", v)} min={0} max={5} />
            <Stepper label="Stories" value={f.stories} onChange={(v) => set("stories", v)} />
            <div className="w-40">
              <Label htmlFor="nc-usage">Paid usage rights</Label>
              <Select id="nc-usage" value={f.usage} onChange={(e) => set("usage", e.target.value)} className="h-10 text-sm">
                {["0", "15", "30", "60", "90"].map((d) => (
                  <option key={d} value={d}>
                    {d === "0" ? "None" : `${d} days`}
                  </option>
                ))}
              </Select>
            </div>
            <div className="w-40">
              <Label htmlFor="nc-excl">Exclusivity</Label>
              <Select id="nc-excl" value={f.exclusivity} onChange={(e) => set("exclusivity", e.target.value)} className="h-10 text-sm">
                {["0", "30", "60", "90"].map((d) => (
                  <option key={d} value={d}>
                    {d === "0" ? "None" : `${d} days`}
                  </option>
                ))}
              </Select>
            </div>
          </div>
          <FieldHint>Deliverables, usage rights and exclusivity all change each creator's fair price, within capped limits.</FieldHint>
        </section>

        <section className="card-surface space-y-4 rounded-xl p-5" aria-label="Budget and timeline">
          {!editId && (
            <label className="flex items-center justify-between gap-4">
              <span>
                <span className="flex items-center gap-1.5 text-sm font-medium">
                  <Users className="size-4 text-accent" aria-hidden /> Book as a collective
                </span>
                <span className="block text-xs text-muted">10 to 50 small creators in one pack, one escrow payment, split by member.</span>
              </span>
              <Switch checked={f.collective} onCheckedChange={(v) => set("collective", v)} aria-label="Book as a collective" />
            </label>
          )}
          {f.collective ? (
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <Label htmlFor="nc-total">Total budget (₹)</Label>
                <Input id="nc-total" inputMode="numeric" value={f.budget_total} onChange={(e) => set("budget_total", e.target.value)} />
              </div>
              <div>
                <Label htmlFor="nc-size">Creators in the pack</Label>
                <Input id="nc-size" type="number" min={10} max={50} value={f.collective_size} onChange={(e) => set("collective_size", Math.max(10, Math.min(50, Number(e.target.value) || 10)))} />
              </div>
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <Label htmlFor="nc-min">Per creator, from (₹)</Label>
                <Input id="nc-min" inputMode="numeric" value={f.budget_min} onChange={(e) => set("budget_min", e.target.value)} />
              </div>
              <div>
                <Label htmlFor="nc-max">Per creator, up to (₹)</Label>
                <Input id="nc-max" inputMode="numeric" value={f.budget_max} onChange={(e) => set("budget_max", e.target.value)} />
              </div>
            </div>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <Label htmlFor="nc-start">Starts (optional)</Label>
              <Input id="nc-start" type="date" value={f.start_date} onChange={(e) => set("start_date", e.target.value)} />
            </div>
            <div>
              <Label htmlFor="nc-deadline">Deadline</Label>
              <Input id="nc-deadline" type="date" value={f.deadline} onChange={(e) => set("deadline", e.target.value)} />
            </div>
          </div>
        </section>

        {problems.length > 0 && (
          <div role="alert" className="rounded-xl border border-warn/40 bg-warn-soft p-4 text-sm">
            <p className="flex items-center gap-1.5 font-medium">
              <AlertCircle className="size-4 text-warn" aria-hidden /> Still needed
            </p>
            <ul className="mt-1.5 list-disc space-y-0.5 pl-5 text-fg-2">
              {problems.map((p) => (
                <li key={p.field + p.message}>{p.message}</li>
              ))}
            </ul>
          </div>
        )}
        <div className="flex flex-wrap items-center justify-end gap-2">
          <Button asChild variant="ghost">
            <Link to={editId ? `/brand/campaigns/${editId}` : "/brand/campaigns"}>Cancel</Link>
          </Button>
          {editId ? (
            <Button type="submit" variant="primary" disabled={!valid} loading={save.isPending}>
              Save changes
            </Button>
          ) : (
            <>
              <Button type="button" variant="outline" disabled={!valid || busy} onClick={() => create.mutate(false)}>
                Save draft
              </Button>
              <Button type="submit" variant="primary" disabled={!valid} loading={create.isPending}>
                Publish
              </Button>
            </>
          )}
        </div>
      </form>
    </div>
  );
}
