import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Building2 } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Wordmark } from "@/components/shared/Wordmark";
import { Button } from "@/components/ui/button";
import { ChipGroup, FieldHint, Input, Label, Segmented, Select, Slider } from "@/components/ui/form";
import { api, post } from "@/lib/api";
import { inr } from "@/lib/format";
import { useTheme } from "@/lib/theme";

interface Meta {
  niches: { id: string; label: string }[];
  languages: { id: string; label: string }[];
  cities: { name: string; state: string }[];
}

const AGES = ["13-17", "18-24", "25-34", "35-44", "45+"];
const BUDGETS = [25_000, 50_000, 100_000, 150_000, 250_000, 500_000, 1_000_000];
const GOALS = ["Awareness", "Sales", "App installs", "Trial", "Sign-ups", "Festive sales"];

export default function BrandOnboarding() {
  useTheme("brand");
  const navigate = useNavigate();
  const meta = useQuery({ queryKey: ["meta"], queryFn: () => api<Meta>("/meta") });
  const [f, setF] = useState({
    name: "",
    category: "",
    niches: [] as string[],
    ages: ["18-24", "25-34"],
    gender: "any" as "any" | "female" | "male",
    cities: [] as string[],
    languages: [] as string[],
    budgetIdx: 2,
    goal: "Awareness",
  });
  const set = <K extends keyof typeof f>(k: K, v: (typeof f)[K]) => setF((p) => ({ ...p, [k]: v }));
  const qc = useQueryClient();
  const create = useMutation({
    mutationFn: () =>
      post<{ id: string }>("/brands", {
        name: f.name,
        category: f.category,
        niches: f.niches,
        ages: f.ages,
        gender: f.gender,
        cities: f.cities,
        languages: f.languages,
        budget_monthly: BUDGETS[f.budgetIdx],
        goal: f.goal,
      }),
    onSuccess: async () => {
      // The new profile is linked to this account on the server; re-read the session to pick it up.
      await qc.invalidateQueries({ queryKey: ["session"] });
      navigate("/brand/campaigns/new");
    },
  });
  const valid = f.name.trim().length >= 2 && f.category.trim().length >= 2 && f.niches.length > 0 && f.ages.length > 0 && f.languages.length > 0;

  return (
    <div className="theme-brand min-h-dvh bg-bg text-fg">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex h-14 max-w-3xl items-center justify-between px-4">
          <Link to="/" className="rounded-lg" aria-label="JodiDar AI home">
            <Wordmark />
          </Link>
          <Link to="/login?role=brand" className="inline-flex items-center gap-1 text-xs font-medium text-muted hover:text-fg">
            <ArrowLeft className="size-3.5" aria-hidden /> Back
          </Link>
        </div>
      </header>
      <main id="main" className="mx-auto max-w-3xl px-4 py-8">
        <p className="flex items-center gap-1.5 text-xs font-medium text-accent">
          <Building2 className="size-3.5" aria-hidden /> Brand onboarding
        </p>
        <h1 className="mt-1 font-display text-2xl font-semibold tracking-tight">Tell us who you want to reach</h1>
        <p className="mt-1 text-sm text-fg-2">We use this to rank creators by audience fit and price each match. About a minute.</p>

        <form
          className="mt-6 space-y-5"
          onSubmit={(e) => {
            e.preventDefault();
            create.mutate();
          }}
        >
          <section className="card-surface grid gap-4 rounded-xl p-5 sm:grid-cols-2">
            <div>
              <Label htmlFor="b-name">Brand name</Label>
              <Input id="b-name" value={f.name} onChange={(e) => set("name", e.target.value)} placeholder="Your brand" />
            </div>
            <div>
              <Label htmlFor="b-cat">Category</Label>
              <Input id="b-cat" value={f.category} onChange={(e) => set("category", e.target.value)} placeholder="For example, Kitchenware" />
            </div>
            <div className="sm:col-span-2">
              <p className="mb-2 text-[13px] font-medium text-fg-2">Creator niches that suit you</p>
              {meta.data && <ChipGroup label="Niches" values={f.niches} onChange={(v) => set("niches", v)} options={meta.data.niches.map((n) => ({ value: n.id, label: n.label }))} />}
            </div>
          </section>

          <section className="card-surface space-y-4 rounded-xl p-5">
            <h2 className="text-sm font-semibold">Target audience</h2>
            <div>
              <p className="mb-2 text-[13px] font-medium text-fg-2">Ages</p>
              <ChipGroup label="Ages" values={f.ages} onChange={(v) => set("ages", v)} options={AGES.map((a) => ({ value: a, label: a }))} />
            </div>
            <div>
              <p className="mb-2 text-[13px] font-medium text-fg-2">Gender</p>
              <Segmented
                label="Gender"
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
              <p className="mb-2 text-[13px] font-medium text-fg-2">Languages</p>
              {meta.data && <ChipGroup label="Languages" values={f.languages} onChange={(v) => set("languages", v)} options={meta.data.languages.map((l) => ({ value: l.id, label: l.label }))} />}
            </div>
            <div>
              <p className="mb-2 text-[13px] font-medium text-fg-2">Priority cities (optional)</p>
              {meta.data && (
                <ChipGroup
                  label="Cities"
                  values={f.cities}
                  onChange={(v) => set("cities", v)}
                  options={meta.data.cities.map((c) => ({ value: c.name, label: c.name }))}
                />
              )}
              <FieldHint>Leave empty for pan-India.</FieldHint>
            </div>
          </section>

          <section className="card-surface grid gap-5 rounded-xl p-5 sm:grid-cols-2">
            <div>
              <p className="text-[13px] font-medium text-fg-2">Monthly creator budget</p>
              <p className="num mt-1 font-display text-2xl font-semibold">{inr(BUDGETS[f.budgetIdx])}</p>
              <Slider className="mt-3" min={0} max={BUDGETS.length - 1} step={1} value={[f.budgetIdx]} onValueChange={([v]) => set("budgetIdx", v)} thumbLabel="Monthly budget" />
            </div>
            <div>
              <Label htmlFor="b-goal">Main goal</Label>
              <Select id="b-goal" value={f.goal} onChange={(e) => set("goal", e.target.value)}>
                {GOALS.map((g) => (
                  <option key={g}>{g}</option>
                ))}
              </Select>
            </div>
          </section>

          {create.isError && (
            <p role="alert" className="text-sm text-danger">
              {(create.error as Error).message}
            </p>
          )}
          <div className="flex justify-end">
            <Button type="submit" variant="primary" disabled={!valid} loading={create.isPending}>
              Continue to your first campaign
            </Button>
          </div>
        </form>
      </main>
    </div>
  );
}
