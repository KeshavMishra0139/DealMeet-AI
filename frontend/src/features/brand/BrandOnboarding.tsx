import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CityOptions } from "@/components/shared/CityOptions";
import { ArrowLeft, Building2, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
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

interface Suggestion {
  name: string;
  website: string | null;
  category: string;
  description: string;
  niches: string[];
  ages: string[];
  gender: "any" | "female" | "male";
  languages: string[];
  budget_monthly: number;
  goal: string;
  by_ai: boolean;
  known: boolean;
}

export default function BrandOnboarding() {
  useTheme("brand");
  const navigate = useNavigate();
  const meta = useQuery({ queryKey: ["meta"], queryFn: () => api<Meta>("/meta") });
  // Step one is just the brand's name and website (prefilled from the account); the AI fills in
  // the rest of the form for the brand to check, change and confirm.
  const [phase, setPhase] = useState<"quick" | "form">("quick");
  const [filled, setFilled] = useState<Suggestion | null>(null);
  const hints = useQuery({ queryKey: ["brand-hints"], queryFn: () => api<{ name: string; website: string | null }>("/brands/setup/hints"), staleTime: Infinity });
  const [f, setF] = useState({
    name: "",
    website: "",
    description: "",
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
  useEffect(() => {
    if (hints.data) setF((p) => ({ ...p, name: p.name || hints.data.name || "", website: p.website || hints.data.website || "" }));
  }, [hints.data]);
  const suggest = useMutation({
    mutationFn: () => post<Suggestion>("/brands/setup/suggest", { name: f.name.trim(), website: f.website.trim() || null }),
    onSuccess: (s) => {
      setF((p) => ({
        ...p,
        category: s.category || p.category,
        description: s.description,
        website: s.website ?? p.website,
        niches: s.niches.length ? s.niches : p.niches,
        ages: s.ages,
        gender: s.gender,
        languages: s.languages,
        budgetIdx: Math.max(0, BUDGETS.indexOf(s.budget_monthly)),
        goal: s.goal,
      }));
      setFilled(s);
      setPhase("form");
    },
    onError: () => setPhase("form"),
  });
  const qc = useQueryClient();
  const create = useMutation({
    mutationFn: () =>
      post<{ id: string }>("/brands", {
        name: f.name,
        category: f.category,
        description: f.description,
        website: f.website.trim() ? (/^https?:\/\//i.test(f.website.trim()) ? f.website.trim() : `https://${f.website.trim()}`) : null,
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
          <Link to="/" className="rounded-lg" aria-label="DealMeet AI home">
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
        <p className="mt-2 text-xs text-muted">
          Already listed as unclaimed?{" "}
          <Link to="/brands" className="text-accent underline underline-offset-2">
            Find your brand's page and claim it
          </Link>{" "}
          instead.
        </p>

        {phase === "quick" ? (
          <form
            className="card-surface mt-6 space-y-4 rounded-xl p-5"
            onSubmit={(e) => {
              e.preventDefault();
              suggest.mutate();
            }}
          >
            <div>
              <p className="flex items-center gap-1.5 text-sm font-semibold">
                <Sparkles className="size-4 text-accent" aria-hidden /> Set up in seconds
              </p>
              <p className="mt-1 text-sm text-fg-2">Tell us your brand. The AI fills in the rest: category, the creators that suit you, your audience and languages. You check it before anything is saved.</p>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <Label htmlFor="q-name">Brand name</Label>
                <Input id="q-name" value={f.name} onChange={(e) => set("name", e.target.value)} placeholder="Your brand" autoFocus />
              </div>
              <div>
                <Label htmlFor="q-web">Website (optional)</Label>
                <Input id="q-web" value={f.website} onChange={(e) => set("website", e.target.value)} placeholder="yourbrand.in" inputMode="url" />
              </div>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <button type="button" className="text-sm text-muted underline-offset-4 hover:text-fg hover:underline" onClick={() => setPhase("form")}>
                Fill it in myself
              </button>
              <Button type="submit" variant="primary" disabled={f.name.trim().length < 2} loading={suggest.isPending}>
                {!suggest.isPending && <Sparkles aria-hidden />} Fill in my profile
              </Button>
            </div>
          </form>
        ) : (
        <form
          className="mt-6 space-y-5"
          onSubmit={(e) => {
            e.preventDefault();
            create.mutate();
          }}
        >
          {filled && (
            <p className="flex items-start gap-2 rounded-xl border border-accent/30 bg-accent-soft p-3 text-sm text-fg">
              <Sparkles className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden />
              {filled.by_ai
                ? filled.known
                  ? `Filled in by AI from what it knows about ${filled.name}. Check it and change anything.`
                  : `Filled in by AI from your brand's name. It's a best guess: check it and change anything.`
                : "We filled in what we could. Add your category and the creator niches that suit you."}
            </p>
          )}
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
              <Select
                aria-label="Add a priority city"
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
        )}
      </main>
    </div>
  );
}
