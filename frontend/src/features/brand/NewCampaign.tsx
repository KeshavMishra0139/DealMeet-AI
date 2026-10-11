import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowLeft, Minus, Plus, Users } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { ChipGroup, FieldHint, Input, Label, Segmented, Select, Switch, Textarea } from "@/components/ui/form";
import { api, post } from "@/lib/api";
import { useBrandId } from "@/lib/session";
import { useBrand } from "./BrandShell";

interface Meta {
  niches: { id: string; label: string }[];
  languages: { id: string; label: string; native: string }[];
}

const REGIONS = ["North", "South", "East", "West", "Central", "Northeast"];

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

export default function NewCampaign() {
  const brandId = useBrandId();
  const brand = useBrand();
  const navigate = useNavigate();
  const meta = useQuery({ queryKey: ["meta"], queryFn: () => api<Meta>("/meta") });
  const [f, setF] = useState({
    title: "",
    summary: "",
    niches: [] as string[],
    languages: [] as string[],
    scope: "pan" as "pan" | "regions",
    regions: [] as string[],
    collective: false,
    collective_size: 20,
    budget_min: "5000",
    budget_max: "20000",
    budget_total: "100000",
    reels: 1,
    stories: 2,
    usage: "30",
    exclusivity: "0",
    deadline: "",
  });
  const set = <K extends keyof typeof f>(k: K, v: (typeof f)[K]) => setF((p) => ({ ...p, [k]: v }));
  const num = (s: string) => Number(s.replace(/[^\d]/g, "")) || 0;

  const create = useMutation({
    mutationFn: () =>
      post<{ id: string }>(`/brands/${brandId}/campaigns`, {
        title: f.title,
        summary: f.summary,
        niches: f.niches,
        languages: f.languages,
        regions: f.scope === "pan" ? ["Pan-India"] : f.regions,
        collective: f.collective,
        collective_size: f.collective_size,
        budget_min: num(f.budget_min),
        budget_max: num(f.budget_max),
        budget_total: num(f.budget_total),
        reels: f.reels,
        stories: f.stories,
        usage_rights_days: num(f.usage),
        exclusivity_days: num(f.exclusivity),
        deadline: f.deadline || null,
      }),
    onSuccess: ({ id }) => navigate(`/brand/campaigns/${id}`),
  });

  const valid = f.title.trim().length >= 4 && f.summary.trim().length >= 10 && f.niches.length > 0 && f.languages.length > 0;

  return (
    <div className="max-w-3xl">
      <Link to="/brand/campaigns" className="inline-flex items-center gap-1 text-xs font-medium text-muted hover:text-fg">
        <ArrowLeft className="size-3.5" aria-hidden /> Campaigns
      </Link>
      <h1 className="mt-2 font-display text-2xl font-semibold tracking-tight">New campaign</h1>
      <p className="mt-1 text-sm text-fg-2">
        Describe the brief. We rank creators who fit {brand.data ? brand.data.name : "your brand"}'s audience and price each match fairly.
      </p>

      <form
        className="mt-6 space-y-5"
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate();
        }}
      >
        <section className="card-surface space-y-4 rounded-xl p-5">
          <div>
            <Label htmlFor="nc-title">Title</Label>
            <Input id="nc-title" value={f.title} onChange={(e) => set("title", e.target.value)} placeholder="For example, Winter drop: anime hoodies" />
          </div>
          <div>
            <Label htmlFor="nc-sum">Brief</Label>
            <Textarea id="nc-sum" value={f.summary} onChange={(e) => set("summary", e.target.value)} placeholder="What creators should make, and what a great post looks like" />
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
        </section>

        <section className="card-surface space-y-4 rounded-xl p-5">
          <div className="flex flex-wrap gap-6">
            <Stepper label="Reels" value={f.reels} onChange={(v) => set("reels", v)} min={1} max={5} />
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

        <section className="card-surface space-y-4 rounded-xl p-5">
          <label className="flex items-center justify-between gap-4">
            <span>
              <span className="flex items-center gap-1.5 text-sm font-medium">
                <Users className="size-4 text-accent" aria-hidden /> Book as a collective
              </span>
              <span className="block text-xs text-muted">10 to 50 small creators in one pack, one escrow payment, split by member.</span>
            </span>
            <Switch checked={f.collective} onCheckedChange={(v) => set("collective", v)} aria-label="Book as a collective" />
          </label>
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
          <div className="w-48">
            <Label htmlFor="nc-deadline">Deadline</Label>
            <Input id="nc-deadline" type="date" value={f.deadline} onChange={(e) => set("deadline", e.target.value)} />
          </div>
        </section>

        {create.isError && (
          <p role="alert" className="text-sm text-danger">
            {(create.error as Error).message}
          </p>
        )}
        <div className="flex items-center justify-end gap-2">
          <Button asChild variant="ghost">
            <Link to="/brand/campaigns">Cancel</Link>
          </Button>
          <Button type="submit" variant="primary" disabled={!valid} loading={create.isPending}>
            Create and see matches
          </Button>
        </div>
      </form>
    </div>
  );
}
