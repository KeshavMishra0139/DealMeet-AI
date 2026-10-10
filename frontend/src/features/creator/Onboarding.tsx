import { useMutation, useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowLeft, ArrowRight, Check, Instagram, Lock, Sparkles, Youtube } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ErrorState } from "@/components/shared/Bits";
import { Wordmark } from "@/components/shared/Wordmark";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChipGroup, FieldHint, Input, Label, Progress, Select, Slider, Switch, Textarea } from "@/components/ui/form";
import { Dialog, DialogContent } from "@/components/ui/overlays";
import { api, post } from "@/lib/api";
import { inr } from "@/lib/format";
import { setPersona } from "@/lib/session";
import { useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";

interface Meta {
  niches: { id: string; label: string }[];
  languages: { id: string; label: string; native: string }[];
  stages: { id: string; label: string }[];
  income_types: { id: string; label: string }[];
  formats: { id: string; label: string }[];
  cities: { name: string; state: string; region: string }[];
}

interface TagResult {
  tags: { caption: string; language_label: string; niche_label: string; tone: string; brand_safety_flags: string[] }[];
  source: string;
  summary: { language: string; niche: string | null; language_label: string; niche_label: string | null } | null;
}

const GOAL_STEPS = [2_000, 5_000, 10_000, 15_000, 25_000, 50_000, 75_000, 100_000, 150_000, 200_000];
const EXPERTISE = ["Chartered Accountant", "Certified yoga teacher", "Software developer", "Home cook", "School teacher", "Fitness trainer"];
const STEP_TITLES = ["What do you make?", "Where are you now?", "What do you want to earn?", "Your language and city", "Connect and choose what brands see"];

type Form = {
  name: string;
  niche: string;
  formats: string[];
  platforms: string[];
  audience_stage: string;
  followers: string;
  expertise: string;
  goalIdx: number;
  income_types: string[];
  languages: string[];
  city: string;
  captions: string;
  connected: { instagram: boolean; youtube: boolean };
  discoverable: boolean;
  scopes: { stats: boolean; demographics: boolean; rate_card: boolean };
};

export default function Onboarding() {
  useTheme("creator");
  const navigate = useNavigate();
  const meta = useQuery({ queryKey: ["meta"], queryFn: () => api<Meta>("/meta") });
  const [step, setStep] = useState(0);
  const [f, setF] = useState<Form>({
    name: "",
    niche: "",
    formats: ["reels"],
    platforms: ["instagram"],
    audience_stage: "",
    followers: "",
    expertise: "",
    goalIdx: 2,
    income_types: [],
    languages: [],
    city: "",
    captions: "",
    connected: { instagram: false, youtube: false },
    discoverable: true,
    scopes: { stats: true, demographics: false, rate_card: false },
  });
  const set = <K extends keyof Form>(k: K, v: Form[K]) => setF((p) => ({ ...p, [k]: v }));
  const [oauth, setOauth] = useState<null | "instagram" | "youtube">(null);

  const tags = useMutation({
    mutationFn: () => post<TagResult>("/ai/tag", { captions: f.captions.split("\n").map((s) => s.trim()).filter(Boolean).slice(0, 8) }),
  });
  const create = useMutation({
    mutationFn: () =>
      post<{ id: string }>("/creators", {
        name: f.name.trim(),
        niche: f.niche,
        formats: f.formats,
        platforms: f.platforms,
        audience_stage: f.audience_stage,
        followers: f.followers ? Number(f.followers.replace(/[^\d]/g, "")) : null,
        income_goal: GOAL_STEPS[f.goalIdx],
        income_types: f.income_types,
        languages: f.languages,
        city: f.city,
        expertise: f.expertise.trim() || null,
        captions: f.captions.split("\n").map((s) => s.trim()).filter(Boolean).slice(0, 8),
        connected: f.connected,
        discoverable: f.discoverable,
        consent_defaults: f.scopes,
      }),
    onSuccess: ({ id }) => {
      setPersona("creator", id);
      navigate("/creator");
    },
  });

  const valid = [
    f.name.trim().length > 0 && !!f.niche && f.formats.length > 0,
    !!f.audience_stage,
    f.income_types.length > 0,
    f.languages.length > 0 && !!f.city,
    true,
  ];
  const secondsLeft = Math.max(15, (5 - step) * 22);

  return (
    <div className="theme-creator grain relative min-h-dvh">
      <div className="aurora" aria-hidden>
        <span />
      </div>
      <div className="relative z-10 mx-auto flex min-h-dvh max-w-xl flex-col px-4 py-5 sm:py-8">
        <header className="flex items-center justify-between">
          <Link to="/" aria-label="JodiDar AI home" className="rounded-lg">
            <Wordmark />
          </Link>
          <span className="text-xs text-muted">About {secondsLeft} seconds left</span>
        </header>
        <nav aria-label="Onboarding progress" className="mt-6">
          <div className="mb-2 flex justify-between text-xs text-muted">
            <span>Step {step + 1} of 5</span>
            <span>Under 2 minutes</span>
          </div>
          <Progress value={((step + 1) / 5) * 100} label={`Step ${step + 1} of 5`} />
        </nav>

        <main id="main" className="mt-8 flex-1">
          {meta.isError && <ErrorState error={meta.error} onRetry={() => meta.refetch()} />}
          {meta.data && (
            <AnimatePresence mode="wait">
              <motion.section
                key={step}
                initial={{ opacity: 0, x: 16 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -16 }}
                transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
                aria-labelledby="step-title"
              >
                <h1 id="step-title" className="font-display text-[26px] font-semibold leading-tight sm:text-[30px]">
                  {STEP_TITLES[step]}
                </h1>

                {step === 0 && (
                  <div className="mt-6 space-y-6">
                    <div>
                      <Label htmlFor="name">Your name or channel name</Label>
                      <Input id="name" value={f.name} onChange={(e) => set("name", e.target.value)} placeholder="For example, Kitchen with Meena" autoComplete="nickname" />
                    </div>
                    <div>
                      <p className="mb-2 text-[13px] font-medium text-fg-2">Your niche</p>
                      <ChipGroup
                        label="Niche"
                        values={f.niche ? [f.niche] : []}
                        onChange={(v) => set("niche", v[v.length - 1] ?? "")}
                        options={meta.data.niches.map((n) => ({ value: n.id, label: n.label }))}
                      />
                    </div>
                    <div>
                      <p className="mb-2 text-[13px] font-medium text-fg-2">Formats you post</p>
                      <ChipGroup label="Formats" values={f.formats} onChange={(v) => set("formats", v)} options={meta.data.formats.map((x) => ({ value: x.id, label: x.label }))} />
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
                  </div>
                )}

                {step === 1 && (
                  <div className="mt-6 space-y-6">
                    <div role="radiogroup" aria-label="Audience stage" className="grid gap-2">
                      {meta.data.stages.map((s) => (
                        <button
                          key={s.id}
                          type="button"
                          role="radio"
                          aria-checked={f.audience_stage === s.id}
                          onClick={() => set("audience_stage", s.id)}
                          className={cn(
                            "flex min-h-12 items-center justify-between rounded-2xl border px-4 text-left text-[15px] transition-colors",
                            f.audience_stage === s.id ? "border-accent bg-accent-soft text-fg" : "border-line-strong bg-surface text-fg-2 hover:border-accent/60",
                          )}
                        >
                          {s.label === "0 followers" ? "Just starting (0 followers)" : `${s.label} followers`}
                          {f.audience_stage === s.id && <Check className="size-4 text-accent" aria-hidden />}
                        </button>
                      ))}
                    </div>
                    <div>
                      <Label htmlFor="followers">Exact follower count (optional)</Label>
                      <Input id="followers" inputMode="numeric" value={f.followers} onChange={(e) => set("followers", e.target.value)} placeholder="2,000" />
                    </div>
                    <div>
                      <Label htmlFor="expertise">A real skill you could charge for (optional)</Label>
                      <Input id="expertise" value={f.expertise} onChange={(e) => set("expertise", e.target.value)} placeholder="For example, Chartered Accountant" />
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {EXPERTISE.map((x) => (
                          <button key={x} type="button" onClick={() => set("expertise", x)} className="rounded-full border border-line px-2.5 py-1 text-xs text-fg-2 hover:border-accent hover:text-fg">
                            {x}
                          </button>
                        ))}
                      </div>
                      <FieldHint>With a skill and a small audience, we'll suggest services and products first.</FieldHint>
                    </div>
                  </div>
                )}

                {step === 2 && (
                  <div className="mt-6 space-y-7">
                    <div>
                      <p className="text-[13px] font-medium text-fg-2">Monthly income goal</p>
                      <p className="num mt-1 font-display text-4xl font-semibold">
                        <span className="text-gradient">{inr(GOAL_STEPS[f.goalIdx])}</span>
                        <span className="ml-2 font-sans text-sm font-normal text-muted">a month</span>
                      </p>
                      <Slider
                        className="mt-4"
                        min={0}
                        max={GOAL_STEPS.length - 1}
                        step={1}
                        value={[f.goalIdx]}
                        onValueChange={([v]) => set("goalIdx", v)}
                        thumbLabel="Monthly income goal"
                      />
                      <div className="num mt-1.5 flex justify-between text-[11px] text-muted">
                        <span>₹2K</span>
                        <span>₹2L</span>
                      </div>
                      <FieldHint>We'll show how each path adds up against this goal, as a range.</FieldHint>
                    </div>
                    <div>
                      <p className="mb-2 text-[13px] font-medium text-fg-2">Income you'd like</p>
                      <ChipGroup
                        label="Preferred income types"
                        values={f.income_types}
                        onChange={(v) => set("income_types", v)}
                        options={meta.data.income_types.map((x) => ({ value: x.id, label: x.label }))}
                      />
                    </div>
                  </div>
                )}

                {step === 3 && (
                  <div className="mt-6 space-y-6">
                    <div>
                      <p className="mb-2 text-[13px] font-medium text-fg-2">Languages you post in (up to 3)</p>
                      <ChipGroup
                        label="Languages"
                        max={3}
                        values={f.languages}
                        onChange={(v) => set("languages", v)}
                        options={meta.data.languages.map((l) => ({ value: l.id, label: l.native === l.label ? l.label : `${l.native} · ${l.label}` }))}
                      />
                    </div>
                    <div>
                      <Label htmlFor="city">City</Label>
                      <Select id="city" value={f.city} onChange={(e) => set("city", e.target.value)}>
                        <option value="">Choose your city</option>
                        {meta.data.cities.map((c) => (
                          <option key={c.name} value={c.name}>
                            {c.name}, {c.state}
                          </option>
                        ))}
                      </Select>
                    </div>
                    <div>
                      <Label htmlFor="captions">Paste 2 or 3 of your captions (optional)</Label>
                      <Textarea
                        id="captions"
                        value={f.captions}
                        onChange={(e) => set("captions", e.target.value)}
                        placeholder={"One per line, in any language\n10 நிமிடத்தில் ரவா உப்புமா"}
                      />
                      <div className="mt-2 flex items-center gap-2">
                        <Button type="button" variant="outline" size="sm" disabled={!f.captions.trim()} loading={tags.isPending} onClick={() => tags.mutate()}>
                          {!tags.isPending && <Sparkles aria-hidden />} Read my captions
                        </Button>
                        <span className="text-xs text-muted">Language, niche, tone and brand safety</span>
                      </div>
                      {tags.data && (
                        <ul className="mt-3 space-y-2" aria-live="polite">
                          {tags.data.tags.map((t) => (
                            <li key={t.caption} className="rounded-xl border border-line bg-surface p-2.5 text-[13px]">
                              <p className="truncate text-fg">{t.caption}</p>
                              <div className="mt-1.5 flex flex-wrap gap-1.5">
                                <Badge size="sm" variant="accent">{t.language_label}</Badge>
                                <Badge size="sm">{t.niche_label}</Badge>
                                <Badge size="sm">{t.tone}</Badge>
                                <Badge size="sm" variant={t.brand_safety_flags.length ? "warn" : "success"}>
                                  {t.brand_safety_flags.length ? t.brand_safety_flags.join(", ") : "Brand safe"}
                                </Badge>
                              </div>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </div>
                )}

                {step === 4 && (
                  <div className="mt-6 space-y-6">
                    <p className="text-[15px] text-fg-2">
                      Optional. In this demo the sandbox login fills in sample insights, marked simulated. We never read accounts that haven't
                      connected, and we never scrape.
                    </p>
                    <div className="grid gap-2 sm:grid-cols-2">
                      {(["instagram", "youtube"] as const).map((p) => {
                        const Icon = p === "instagram" ? Instagram : Youtube;
                        const on = f.connected[p];
                        return (
                          <button
                            key={p}
                            type="button"
                            onClick={() => (on ? set("connected", { ...f.connected, [p]: false }) : setOauth(p))}
                            className={cn(
                              "flex min-h-14 items-center gap-3 rounded-2xl border px-4 text-left transition-colors",
                              on ? "border-success/50 bg-success-soft" : "border-line-strong bg-surface hover:border-accent/60",
                            )}
                          >
                            <Icon className="size-5" aria-hidden />
                            <span className="flex-1">
                              <span className="block text-sm font-medium">{p === "instagram" ? "Instagram" : "YouTube"}</span>
                              <span className="block text-xs text-muted">{on ? "Connected (demo sandbox)" : "Connect via official login"}</span>
                            </span>
                            {on && <Check className="size-4 text-success" aria-hidden />}
                          </button>
                        );
                      })}
                    </div>
                    <div className="rounded-2xl border border-line bg-surface p-4">
                      <label className="flex items-center justify-between gap-4">
                        <span>
                          <span className="block font-medium">Let brands discover me</span>
                          <span className="block text-xs text-muted">You can turn this off any time.</span>
                        </span>
                        <Switch checked={f.discoverable} onCheckedChange={(v) => set("discoverable", v)} aria-label="Let brands discover me" />
                      </label>
                      <div className={cn("mt-4 space-y-3 border-t border-line pt-4", !f.discoverable && "opacity-50")}>
                        <p className="text-xs font-semibold uppercase tracking-[0.1em] text-muted">What brands can see by default</p>
                        {(
                          [
                            ["stats", "Reach and engagement stats"],
                            ["demographics", "Audience demographics"],
                            ["rate_card", "Your rate card"],
                          ] as const
                        ).map(([k, label]) => (
                          <label key={k} className="flex items-center justify-between gap-4 text-sm">
                            {label}
                            <Switch
                              disabled={!f.discoverable}
                              checked={f.scopes[k]}
                              onCheckedChange={(v) => set("scopes", { ...f.scopes, [k]: v })}
                              aria-label={label}
                            />
                          </label>
                        ))}
                        <p className="flex items-center gap-1.5 text-xs text-muted">
                          <Lock className="size-3.5" aria-hidden /> You can change this per brand later, with a full audit trail.
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </motion.section>
            </AnimatePresence>
          )}
        </main>

        {create.isError && (
          <p role="alert" className="mb-3 text-sm text-danger">
            {(create.error as Error).message}
          </p>
        )}
        <footer className="sticky bottom-0 -mx-4 mt-8 flex items-center justify-between gap-3 border-t border-line bg-[var(--bg)]/80 px-4 py-3 backdrop-blur-xl sm:static sm:mx-0 sm:border-0 sm:bg-transparent sm:px-0 sm:backdrop-blur-none">
          <Button variant="ghost" onClick={() => (step === 0 ? navigate("/login?role=creator") : setStep(step - 1))}>
            <ArrowLeft aria-hidden /> Back
          </Button>
          {step < 4 ? (
            <Button variant="primary" size="lg" disabled={!valid[step]} onClick={() => setStep(step + 1)}>
              Next <ArrowRight aria-hidden />
            </Button>
          ) : (
            <Button variant="primary" size="lg" loading={create.isPending} onClick={() => create.mutate()}>
              {!create.isPending && <Sparkles aria-hidden />} Build my plan
            </Button>
          )}
        </footer>
      </div>

      <Dialog open={oauth !== null} onOpenChange={(o) => !o && setOauth(null)}>
        <DialogContent
          title={oauth === "youtube" ? "Sign in with Google" : "Log in with Instagram"}
          description="Official login (demo sandbox). No password is shared with JodiDar AI."
        >
          <div className="rounded-2xl border border-line bg-surface p-4">
            <p className="text-sm font-medium">JodiDar AI would like to:</p>
            <ul className="mt-2 space-y-1.5 text-sm text-fg-2">
              {(oauth === "youtube"
                ? ["See your channel's basic info", "See analytics for your videos"]
                : ["Read your profile info", "Read insights for your reels", "Read your audience summary"]
              ).map((s) => (
                <li key={s} className="flex gap-2">
                  <Check className="mt-0.5 size-4 text-success" aria-hidden />
                  {s}
                </li>
              ))}
            </ul>
            <p className="mt-3 text-xs text-muted">It can't post, message or follow on your behalf. Disconnect any time.</p>
          </div>
          <div className="mt-5 flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setOauth(null)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={async () => {
                if (!oauth) return;
                await post(`/oauth/${oauth}/authorize`);
                set("connected", { ...f.connected, [oauth]: true });
                setOauth(null);
              }}
            >
              Allow
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
