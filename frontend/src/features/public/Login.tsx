import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowRight, Building2, Sparkles, UserPlus } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Avatar, ErrorState } from "@/components/shared/Bits";
import { Wordmark } from "@/components/shared/Wordmark";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Segmented, Skeleton } from "@/components/ui/form";
import { api, post } from "@/lib/api";
import { firebaseEnabled, signInWithGoogle } from "@/lib/firebase";
import { setPersona } from "@/lib/session";
import { useTheme } from "@/lib/theme";
import type { Health, Persona } from "@/lib/types";
import { cn } from "@/lib/utils";

const HUES: Record<string, number> = { cr_a: 268, cr_b: 24, br_senpai: 268, br_thalam: 24 };

export default function Login() {
  useTheme("creator");
  const [params] = useSearchParams();
  const [role, setRole] = useState<"creator" | "brand">(params.get("role") === "brand" ? "brand" : "creator");
  const [fbUser, setFbUser] = useState<string | null>(null);
  const navigate = useNavigate();
  const personas = useQuery({ queryKey: ["personas"], queryFn: () => api<Persona[]>("/auth/personas") });
  const health = useQuery({ queryKey: ["health"], queryFn: () => api<Health>("/health") });

  const login = useMutation({
    mutationFn: (p: Persona) => post<{ persona: Persona }>("/auth/demo", { persona: p.id }),
    onSuccess: ({ persona }) => {
      if (persona.id === "new_creator") return navigate("/creator/onboarding");
      if (persona.id === "new_brand") return navigate("/brand/onboarding");
      setPersona(persona.role, persona.id);
      navigate(persona.role === "creator" ? "/creator" : "/brand");
    },
  });

  const list = personas.data?.filter((p) => p.role === role) ?? [];

  return (
    <div className="theme-creator grain relative min-h-dvh">
      <div className="aurora" aria-hidden>
        <span />
      </div>
      <div className="relative z-10 mx-auto flex min-h-dvh max-w-lg flex-col px-4 py-5 sm:py-10">
        <header>
          <Link to="/" className="inline-block rounded-lg" aria-label="JodiDar AI home">
            <Wordmark />
          </Link>
        </header>
        <main id="main" className="mt-10 flex-1 sm:mt-16">
          <h1 className="font-display text-[28px] font-semibold leading-tight sm:text-[32px]">Who's using JodiDar today?</h1>
          <p className="mt-2 text-[15px] text-fg-2">
            {firebaseEnabled
              ? "Sign in, then pick a demo profile. Every profile runs on seeded data."
              : "Demo login: no account needed. Pick a profile to explore."}
          </p>

          {firebaseEnabled && (
            <div className="mt-5">
              {fbUser ? (
                <p className="text-sm text-success">Signed in as {fbUser}</p>
              ) : (
                <Button
                  variant="outline"
                  onClick={async () => {
                    const name = await signInWithGoogle();
                    if (name) setFbUser(name);
                  }}
                >
                  Continue with Google
                </Button>
              )}
            </div>
          )}

          <Segmented
            className="mt-6"
            label="Choose a side"
            value={role}
            onChange={setRole}
            options={[
              { value: "creator", label: "I'm a creator" },
              { value: "brand", label: "I'm a brand" },
            ]}
          />

          <div className="mt-4 space-y-2.5" aria-live="polite">
            {personas.isLoading &&
              Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-[76px] rounded-2xl" />)}
            {personas.isError && <ErrorState error={personas.error} onRetry={() => personas.refetch()} />}
            {list.map((p) => {
              const isNew = p.id.startsWith("new_");
              const busy = login.isPending && login.variables?.id === p.id;
              return (
                <button
                  key={p.id}
                  onClick={() => login.mutate(p)}
                  disabled={login.isPending}
                  className={cn(
                    "group flex w-full items-center gap-3.5 rounded-2xl border border-line bg-surface p-3.5 text-left backdrop-blur transition-[border-color,transform] duration-200 hover:-translate-y-0.5 hover:border-accent/60 disabled:opacity-70",
                    isNew && "border-dashed",
                  )}
                >
                  {isNew ? (
                    <span className="grid size-11 place-items-center rounded-full bg-surface-3 text-fg-2">
                      {p.role === "creator" ? <UserPlus className="size-5" /> : <Building2 className="size-5" />}
                    </span>
                  ) : (
                    <Avatar name={p.title} hue={HUES[p.id]} size={44} generic={p.id === "cr_a"} />
                  )}
                  <span className="min-w-0 flex-1">
                    <span className="flex flex-wrap items-center gap-2">
                      <span className="font-semibold">{p.title}</span>
                      <Badge size="sm" variant={p.tag === "Reference profile" ? "warn" : "neutral"}>
                        {p.tag}
                      </Badge>
                    </span>
                    <span className="mt-0.5 line-clamp-2 block text-[13px] leading-snug text-muted">{p.subtitle}</span>
                  </span>
                  <ArrowRight
                    className={cn("size-4 shrink-0 text-muted transition-transform group-hover:translate-x-0.5", busy && "animate-pulse")}
                    aria-hidden
                  />
                </button>
              );
            })}
          </div>
          {login.isError && (
            <p role="alert" className="mt-3 text-sm text-danger">
              {(login.error as Error).message}
            </p>
          )}

          <Link
            to="/demo/compare"
            className="mt-6 flex items-center gap-2 rounded-2xl border border-line bg-surface-2 p-3.5 text-sm text-fg-2 hover:text-fg"
          >
            <Sparkles className="size-4 text-accent" aria-hidden />
            Short on time? See Creator A and Creator B side by side.
          </Link>
        </main>
        {health.data && (
          <footer className="mt-8 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-muted">
            <span>Data: {health.data.modes.db}</span>
            <span>AI: {health.data.modes.ai}</span>
            <span>Payments: {health.data.modes.payments}</span>
            <span>Auth: {health.data.modes.auth}</span>
          </footer>
        )}
      </div>
    </div>
  );
}
