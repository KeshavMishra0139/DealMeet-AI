import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ConfirmationResult } from "firebase/auth";
import { ArrowRight, Building2, Phone, Sparkles, UserPlus } from "lucide-react";
import { toast } from "sonner";
import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { safeNext } from "@/components/shared/AuthGate";
import { Avatar, ErrorState } from "@/components/shared/Bits";
import { Wordmark } from "@/components/shared/Wordmark";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { FieldHint, Input, Label, Segmented, Skeleton } from "@/components/ui/form";
import { api } from "@/lib/api";
import { confirmPhoneCode, firebaseEnabled, firebaseMessage, googleIdToken, sendPhoneCode, signOutFirebase } from "@/lib/firebase";
import { forgetAllTokens, rememberDemoToken, type Role, type SessionUser } from "@/lib/session";
import { useHealth } from "@/lib/shared-demo";
import { useTheme } from "@/lib/theme";
import type { Persona } from "@/lib/types";
import { cn } from "@/lib/utils";

const HUES: Record<string, number> = { cr_a: 268, cr_b: 24, br_senpai: 268, br_thalam: 24 };

function homeFor(user: SessionUser) {
  if (user.role === "admin") return "/admin";
  if (user.role === "brand") return user.brand_id ? "/brand" : "/brand/onboarding";
  return user.creator_id ? "/creator" : "/creator/onboarding";
}

export default function Login() {
  useTheme("creator");
  const [params] = useSearchParams();
  const [role, setRole] = useState<Role>(params.get("role") === "brand" ? "brand" : "creator");
  const next = safeNext(params.get("next"));
  const health = useHealth();
  const demo = !!health.data?.demo_mode;

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
        <main id="main" className="mt-10 flex-1 sm:mt-14">
          <h1 className="font-display text-[28px] font-semibold leading-tight sm:text-[32px]">Sign in to JodiDar</h1>
          <p className="mt-2 text-[15px] text-fg-2">
            {demo
              ? "Sign in to your account, or pick a demo profile below. Demo profiles run on sample data that resets."
              : "Creators and brands each have their own account."}
          </p>

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

          <FirebaseSignIn role={role} next={next} serverReady={!!health.data?.modes.auth.includes("firebase")} loaded={!!health.data} />
          <AccountForm role={role} next={next} demo={demo} />
          {demo && <DemoProfiles role={role} next={next} />}

          {demo && (
            <Link
              to="/demo/compare"
              className="mt-6 flex items-center gap-2 rounded-2xl border border-line bg-surface-2 p-3.5 text-sm text-fg-2 hover:text-fg"
            >
              <Sparkles className="size-4 text-accent" aria-hidden />
              Short on time? See Creator A and Creator B side by side.
            </Link>
          )}
        </main>
        {health.data && (
          <footer className="mt-8 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-muted">
            <span>Data: {health.data.modes.db === "mock" ? "in-memory (mock)" : health.data.modes.db}</span>
            <span>AI: {health.data.modes.ai}</span>
            <span>Payments: {health.data.modes.payments}</span>
            <span>Auth: {health.data.modes.auth}</span>
            {health.data.shared_demo && <span className="w-full">Shared live demo: everyone sees the same data, and it resets automatically when idle.</span>}
          </footer>
        )}
      </div>
    </div>
  );
}

/** Where to go after signing in: back where you came from if it's your side of the app. */
function destination(user: SessionUser, next: string | null) {
  const home = homeFor(user);
  const side = home.split("/").slice(0, 2).join("/");
  return next && next.startsWith(side) ? next : home;
}

function FirebaseSignIn({ role, next, serverReady, loaded }: { role: Role; next: string | null; serverReady: boolean; loaded: boolean }) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [busy, setBusy] = useState<null | "google" | "send" | "verify">(null);
  const [error, setError] = useState("");
  const [phoneOpen, setPhoneOpen] = useState(false);
  const [phone, setPhone] = useState("+91 ");
  const [code, setCode] = useState("");
  const [confirmation, setConfirmation] = useState<ConfirmationResult | null>(null);

  if (!loaded) return null;
  if (!firebaseEnabled || !serverReady)
    return <p className="mt-5 text-xs text-muted">Google and phone sign-in aren't configured on this server. Use email and password below.</p>;

  const exchange = async (idToken: string) => {
    // The server verifies the token with Firebase and starts the app's own session.
    const r = await api<{ user: SessionUser; note?: string }>("/auth/firebase", { method: "POST", json: { id_token: idToken, role }, role: null });
    await signOutFirebase();
    forgetAllTokens();
    await qc.invalidateQueries({ queryKey: ["session"] });
    if (r.note) toast.info(r.note);
    navigate(destination(r.user, next));
  };
  const attempt = async (step: "google" | "send" | "verify", fn: () => Promise<void>) => {
    setBusy(step);
    setError("");
    try {
      await fn();
    } catch (e) {
      const msg = firebaseMessage(e);
      if (msg) setError(msg);
    } finally {
      setBusy(null);
    }
  };

  return (
    <section aria-label="Sign in with Google or phone" className="mt-5 space-y-2.5">
      <Button variant="outline" className="w-full" loading={busy === "google"} onClick={() => attempt("google", async () => exchange(await googleIdToken()))}>
        Continue with Google
      </Button>
      {!phoneOpen ? (
        <Button variant="ghost" className="w-full" onClick={() => setPhoneOpen(true)}>
          <Phone aria-hidden /> Use my phone number
        </Button>
      ) : (
        <div className="card-surface space-y-3 rounded-2xl p-4">
          {!confirmation ? (
            <form
              className="space-y-3"
              onSubmit={(e) => {
                e.preventDefault();
                void attempt("send", async () => setConfirmation(await sendPhoneCode(phone.replace(/\s+/g, ""), "recaptcha-anchor")));
              }}
            >
              <Label htmlFor="fb-phone">Phone number</Label>
              <Input id="fb-phone" type="tel" inputMode="tel" autoComplete="tel" value={phone} onChange={(e) => setPhone(e.target.value)} required />
              <FieldHint>We send a one-time code by SMS. Standard SMS rates may apply.</FieldHint>
              <Button type="submit" variant="primary" className="w-full" loading={busy === "send"}>
                Send code
              </Button>
            </form>
          ) : (
            <form
              className="space-y-3"
              onSubmit={(e) => {
                e.preventDefault();
                void attempt("verify", async () => exchange(await confirmPhoneCode(confirmation, code.trim())));
              }}
            >
              <Label htmlFor="fb-code">Code from the SMS</Label>
              <Input id="fb-code" inputMode="numeric" autoComplete="one-time-code" value={code} onChange={(e) => setCode(e.target.value)} required maxLength={8} />
              <Button type="submit" variant="primary" className="w-full" loading={busy === "verify"}>
                Verify and sign in
              </Button>
            </form>
          )}
        </div>
      )}
      <div id="recaptcha-anchor" />
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      <p className="text-xs text-muted">First time? You'll join as {role === "creator" ? "a creator" : "a brand"}, the side picked above. That can't change later.</p>
    </section>
  );
}

function AccountForm({ role, next, demo }: { role: Role; next: string | null; demo: boolean }) {
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const qc = useQueryClient();
  const navigate = useNavigate();
  const submit = useMutation({
    mutationFn: () =>
      mode === "signup"
        ? api<{ user: SessionUser }>("/auth/signup", { method: "POST", json: { name, email, password, role }, role: null })
        : api<{ user: SessionUser }>("/auth/login", { method: "POST", json: { email, password }, role: null }),
    onSuccess: async ({ user }) => {
      // The cookie session now speaks for this browser; demo tokens would shadow it.
      forgetAllTokens();
      await qc.invalidateQueries({ queryKey: ["session"] });
      navigate(destination(user, next));
    },
  });

  return (
    <section aria-labelledby="account" className="card-surface mt-5 rounded-[var(--radius-card)] p-4 sm:p-5">
      <div className="flex items-center justify-between gap-3">
        <h2 id="account" className="font-display text-lg font-semibold">
          {mode === "signin" ? "Sign in" : `Create a ${role} account`}
        </h2>
        <Button variant="ghost" size="sm" onClick={() => setMode(mode === "signin" ? "signup" : "signin")}>
          {mode === "signin" ? "Create an account" : "I have an account"}
        </Button>
      </div>
      <form
        className="mt-3 space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          submit.mutate();
        }}
      >
        {mode === "signup" && (
          <div>
            <Label htmlFor="acc-name">{role === "brand" ? "Your name" : "Your name or channel name"}</Label>
            <Input id="acc-name" value={name} onChange={(e) => setName(e.target.value)} required maxLength={60} autoComplete="name" />
          </div>
        )}
        <div>
          <Label htmlFor="acc-email">Email</Label>
          <Input id="acc-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
        </div>
        <div>
          <Label htmlFor="acc-password">Password</Label>
          <Input
            id="acc-password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={mode === "signup" ? 8 : 1}
            autoComplete={mode === "signup" ? "new-password" : "current-password"}
          />
          {mode === "signup" && <FieldHint>At least 8 characters. Your account is either a creator or a brand, and that can't change later.</FieldHint>}
        </div>
        {submit.isError && (
          <p role="alert" className="text-sm text-danger">
            {(submit.error as Error).message}
          </p>
        )}
        <Button type="submit" variant="primary" className="w-full" loading={submit.isPending}>
          {mode === "signin" ? "Sign in" : "Create account"}
        </Button>
        {demo && mode === "signup" && (
          <p className="text-xs text-muted">Demo mode: accounts made here are sandbox data and are removed when the demo resets.</p>
        )}
      </form>
    </section>
  );
}

function DemoProfiles({ role, next }: { role: Role; next: string | null }) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const personas = useQuery({ queryKey: ["personas"], queryFn: () => api<Persona[]>("/auth/personas", { role: null }) });
  const login = useMutation({
    mutationFn: (p: Persona) => api<{ token: string; persona: Persona }>("/auth/demo", { method: "POST", json: { persona: p.id, cookie: false }, role: null }),
    onSuccess: async ({ token, persona }) => {
      rememberDemoToken(persona.role, token);
      await qc.invalidateQueries({ queryKey: ["session"] });
      if (persona.id === "new_creator") return navigate("/creator/onboarding");
      if (persona.id === "new_brand") return navigate("/brand/onboarding");
      const home = persona.role === "creator" ? "/creator" : "/brand";
      navigate(next && next.startsWith(home) ? next : home);
    },
  });
  const list = personas.data?.filter((p) => p.role === role) ?? [];

  return (
    <section aria-labelledby="demo-profiles" className="mt-6">
      <h2 id="demo-profiles" className="text-xs font-semibold uppercase tracking-[0.12em] text-muted">
        Or explore a demo profile
      </h2>
      <div className="mt-3 space-y-2.5" aria-live="polite">
        {personas.isLoading && Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-[76px] rounded-2xl" />)}
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
                "group flex w-full items-center gap-3.5 rounded-2xl border border-line bg-surface p-3.5 text-left transition-[border-color,transform] duration-200 hover:-translate-y-0.5 hover:border-accent/60 disabled:opacity-70",
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
              <ArrowRight className={cn("size-4 shrink-0 text-muted transition-transform group-hover:translate-x-0.5", busy && "animate-pulse")} aria-hidden />
            </button>
          );
        })}
      </div>
      {login.isError && (
        <p role="alert" className="mt-3 text-sm text-danger">
          {(login.error as Error).message}
        </p>
      )}
    </section>
  );
}
