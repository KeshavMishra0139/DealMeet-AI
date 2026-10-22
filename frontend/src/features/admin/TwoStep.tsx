// Two-step sign-in for admins (services/totp.py on the server): turn it on with an
// authenticator app, keep the recovery codes, and enter a code at each new sign-in. The
// admin routes refuse every request until this session has passed it; this screen only
// decides what to show.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, KeyRound, LogOut, ShieldCheck } from "lucide-react";
import { useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { ErrorState } from "@/components/shared/Bits";
import { QrCode } from "@/components/shared/QrCode";
import { Wordmark } from "@/components/shared/Wordmark";
import { Button } from "@/components/ui/button";
import { FieldHint, Input, Label } from "@/components/ui/form";
import { api } from "@/lib/api";

interface MfaStatus {
  required: boolean;
  enabled: boolean;
  passed: boolean;
  can_set_up: boolean;
  recovery_codes_left: number;
}

const KEY = ["admin", "mfa"];

/** Renders the console only once this session has passed two-step sign-in (or doesn't need it). */
export function TwoStepGate({ children }: { children: ReactNode }) {
  const q = useQuery({ queryKey: KEY, queryFn: () => api<MfaStatus>("/auth/mfa", { role: null }) });
  if (q.isPending) return <div className="min-h-dvh" aria-busy="true" aria-label="Checking two-step sign-in" />;
  if (q.isError)
    return (
      <div className="mx-auto max-w-md p-6">
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      </div>
    );
  if (!q.data.required || q.data.passed) return <>{children}</>;
  return (
    <Frame>
      {q.data.enabled ? <EnterCode /> : q.data.can_set_up ? <SetUp /> : <CantSetUp />}
    </Frame>
  );
}

function Frame({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const signOut = async () => {
    try {
      await api("/auth/logout", { method: "POST", json: {}, role: null });
    } finally {
      qc.clear();
      navigate("/login");
    }
  };
  return (
    <div className="theme-brand grid min-h-dvh place-items-center bg-bg px-4 py-10 text-fg">
      <main id="main" className="w-full max-w-md">
        <div className="flex items-center justify-between">
          <Wordmark />
          <Button size="sm" variant="ghost" onClick={() => void signOut()}>
            <LogOut aria-hidden /> Sign out
          </Button>
        </div>
        <section aria-labelledby="two-step" className="card-surface mt-6 rounded-[var(--radius-card)] p-5">
          <h1 id="two-step" className="flex items-center gap-2 font-display text-lg font-semibold">
            <ShieldCheck className="size-5 text-accent" aria-hidden /> Two-step sign-in
          </h1>
          {children}
        </section>
      </main>
    </div>
  );
}

function CodeField({ id, label, value, onChange, hint }: { id: string; label: string; value: string; onChange: (v: string) => void; hint: string }) {
  return (
    <div>
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} value={value} onChange={(e) => onChange(e.target.value.trim())} autoComplete="one-time-code" inputMode="text" maxLength={12} required />
      <FieldHint>{hint}</FieldHint>
    </div>
  );
}

function CantSetUp() {
  return (
    <p className="mt-3 text-sm leading-relaxed text-fg-2" role="alert">
      Admin accounts need two-step sign-in, and it needs TOKEN_ENC_KEY set on the server so the secret is stored encrypted. Set it (see .env.example), restart
      the server and sign in again.
    </p>
  );
}

function SetUp() {
  const qc = useQueryClient();
  const [code, setCode] = useState("");
  const [saved, setSaved] = useState(false);
  const start = useMutation({ mutationFn: () => api<{ secret: string; uri: string }>("/auth/mfa/setup", { method: "POST", role: null }) });
  const enable = useMutation({
    mutationFn: () => api<{ recovery_codes: string[] }>("/auth/mfa/enable", { method: "POST", json: { code }, role: null }),
  });
  if (enable.data) {
    const codes = enable.data.recovery_codes;
    const file = `data:text/plain;charset=utf-8,${encodeURIComponent(`DealMeet AI admin recovery codes\nEach works once.\n\n${codes.join("\n")}\n`)}`;
    return (
      <div className="mt-3 space-y-4">
        <p className="text-sm leading-relaxed text-fg-2">
          Two-step sign-in is on. Keep these recovery codes somewhere safe, away from your phone. Each one works once if you lose the app. They won't be shown again.
        </p>
        <ul className="num grid grid-cols-2 gap-2 rounded-xl border border-line bg-surface-2 p-3 font-mono text-sm" aria-label="Recovery codes">
          {codes.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
        <Button asChild size="sm" variant="outline">
          <a href={file} download="dealmeet-recovery-codes.txt">
            <Download aria-hidden /> Download the codes
          </a>
        </Button>
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" className="mt-0.5 size-4 accent-[var(--accent)]" checked={saved} onChange={(e) => setSaved(e.target.checked)} />
          I've saved these codes
        </label>
        <Button variant="primary" className="w-full" disabled={!saved} onClick={() => void qc.invalidateQueries({ queryKey: KEY })}>
          Open the admin console
        </Button>
      </div>
    );
  }
  if (!start.data)
    return (
      <div className="mt-3 space-y-4">
        <p className="text-sm leading-relaxed text-fg-2">
          Admin accounts sign in with a password and a code from an authenticator app (Google Authenticator, Microsoft Authenticator, 1Password and others). It
          takes a minute.
        </p>
        {start.isError && (
          <p role="alert" className="text-sm text-danger">
            {(start.error as Error).message}
          </p>
        )}
        <Button variant="primary" className="w-full" loading={start.isPending} onClick={() => start.mutate()}>
          <KeyRound aria-hidden /> Set up two-step sign-in
        </Button>
      </div>
    );
  return (
    <form
      className="mt-3 space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        enable.mutate();
      }}
    >
      <p className="text-sm leading-relaxed text-fg-2">Scan this with your authenticator app, then enter the 6-digit code it shows.</p>
      <div className="flex justify-center">
        <QrCode url={start.data.uri} label="QR code to add DealMeet AI to your authenticator app" size={176} downloadable={false} />
      </div>
      <p className="text-xs text-muted">
        Can't scan? Enter this key in the app instead:{" "}
        <code className="num break-all rounded bg-surface-2 px-1.5 py-0.5 font-mono text-fg">{start.data.secret.match(/.{1,4}/g)?.join(" ")}</code>
      </p>
      <CodeField id="mfa-setup-code" label="Code from the app" value={code} onChange={setCode} hint="6 digits. A new one appears every 30 seconds." />
      {enable.isError && (
        <p role="alert" className="text-sm text-danger">
          {(enable.error as Error).message}
        </p>
      )}
      <Button type="submit" variant="primary" className="w-full" loading={enable.isPending} disabled={!/^\d{6}$/.test(code)}>
        Turn on two-step sign-in
      </Button>
    </form>
  );
}

function EnterCode() {
  const qc = useQueryClient();
  const [code, setCode] = useState("");
  const verify = useMutation({
    mutationFn: () => api<{ recovery_codes_left: number }>("/auth/mfa/verify", { method: "POST", json: { code }, role: null }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: KEY }),
  });
  return (
    <form
      className="mt-3 space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        verify.mutate();
      }}
    >
      <CodeField
        id="mfa-code"
        label="Code from your authenticator app"
        value={code}
        onChange={setCode}
        hint="Lost the app? Enter one of your recovery codes (like 1a2b-3c4d) instead."
      />
      {verify.isError && (
        <p role="alert" className="text-sm text-danger">
          {(verify.error as Error).message}
        </p>
      )}
      <Button type="submit" variant="primary" className="w-full" loading={verify.isPending} disabled={code.length < 6}>
        Continue
      </Button>
    </form>
  );
}
