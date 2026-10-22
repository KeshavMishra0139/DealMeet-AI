// Where emailed links land: /login/reset (choose a new password) and /verify-email
// (confirm an address). The address carries a one-time token; it's taken out of the address
// bar straight away, and sent to the API only when the person acts (or, for verification,
// once on load).
import { useMutation } from "@tanstack/react-query";
import { CheckCircle2, KeyRound, Loader2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { Wordmark } from "@/components/shared/Wordmark";
import { Button } from "@/components/ui/button";
import { FieldHint, Input, Label } from "@/components/ui/form";
import { api } from "@/lib/api";
import type { SessionUser } from "@/lib/session";
import { useTheme } from "@/lib/theme";
import { useFinishSignIn } from "./signin";

function useLinkToken(path: string) {
  const [params] = useSearchParams();
  const [token] = useState(() => params.get("t"));
  useEffect(() => {
    window.history.replaceState(window.history.state, "", path); // keep it out of history
  }, [path]);
  return token;
}

function Frame({ title, children }: { title: string; children: React.ReactNode }) {
  useTheme("creator");
  return (
    <div className="theme-creator relative grid min-h-dvh place-items-center px-4 py-10">
      <main id="main" className="w-full max-w-sm">
        <div className="text-center">
          <Wordmark />
        </div>
        <section aria-labelledby="link-title" className="card-surface mt-8 rounded-[var(--radius-card)] p-5">
          <h1 id="link-title" className="font-display text-lg font-semibold">
            {title}
          </h1>
          {children}
        </section>
      </main>
    </div>
  );
}

function Missing({ what }: { what: string }) {
  return (
    <div className="mt-3 space-y-4">
      <p role="alert" className="text-sm text-danger">
        This link is missing its code. Open the {what} email again, or ask for a new one.
      </p>
      <Button asChild variant="primary" className="w-full">
        <Link to="/login">Go to sign-in</Link>
      </Button>
    </div>
  );
}

/** /login/reset?t=…: choose a new password. Signs every other device out, and this one in. */
export function ResetPassword() {
  const token = useLinkToken("/login/reset");
  const finish = useFinishSignIn();
  const [password, setPassword] = useState("");
  const [again, setAgain] = useState("");
  const reset = useMutation({
    mutationFn: () => api<{ user: SessionUser }>("/auth/password/reset", { method: "POST", json: { token, password }, role: null }),
    onSuccess: ({ user }) => {
      toast.success("Your new password is set", { description: "Every other device was signed out." });
      void finish(user, null);
    },
  });
  if (!token) return <Frame title="Choose a new password"><Missing what="password reset" /></Frame>;
  const mismatch = again.length > 0 && again !== password;
  return (
    <Frame title="Choose a new password">
      <form
        className="mt-3 space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          reset.mutate();
        }}
      >
        <div>
          <Label htmlFor="new-password">New password</Label>
          <Input id="new-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} maxLength={128} autoComplete="new-password" />
          <FieldHint>At least 8 characters. This signs you out on every other device.</FieldHint>
        </div>
        <div>
          <Label htmlFor="new-password-again">The same password again</Label>
          <Input
            id="new-password-again"
            type="password"
            value={again}
            onChange={(e) => setAgain(e.target.value)}
            required
            autoComplete="new-password"
            aria-invalid={mismatch || undefined}
            aria-describedby={mismatch ? "new-password-mismatch" : undefined}
          />
          {mismatch && (
            <p id="new-password-mismatch" className="mt-1 text-xs text-danger">
              The two passwords aren't the same.
            </p>
          )}
        </div>
        {reset.isError && (
          <p role="alert" className="text-sm text-danger">
            {(reset.error as Error).message}{" "}
            <Link to="/login" className="font-medium underline underline-offset-4">
              Ask for a new link
            </Link>
          </p>
        )}
        <Button type="submit" variant="primary" className="w-full" loading={reset.isPending} disabled={password.length < 8 || password !== again}>
          <KeyRound aria-hidden /> Set password and sign in
        </Button>
      </form>
    </Frame>
  );
}

/** /verify-email?t=…: confirms the address once, on load. Works signed in or not. */
export function VerifyEmail() {
  const token = useLinkToken("/verify-email");
  const started = useRef(false);
  const [state, setState] = useState<{ email?: string; role?: string; error?: string }>({});
  useEffect(() => {
    // The token works once, so it's sent once (React's development double-run included).
    if (!token || started.current) return;
    started.current = true;
    api<{ email: string; role: string }>("/auth/email/verify", { method: "POST", json: { token }, role: null })
      .then((r) => setState(r))
      .catch((e: Error) => setState({ error: e.message }));
  }, [token]);
  if (!token) return <Frame title="Confirm your email"><Missing what="confirmation" /></Frame>;
  const home = state.role === "brand" ? "/brand" : state.role === "admin" ? "/admin" : "/creator";
  return (
    <Frame title="Confirm your email">
      <div className="mt-3 space-y-4" aria-live="polite">
        {state.email ? (
          <>
            <p className="flex items-start gap-2 text-sm text-fg-2">
              <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-success" aria-hidden /> {state.email} is confirmed. Thank you.
            </p>
            <Button asChild variant="primary" className="w-full">
              <Link to={home}>Open DealMeet AI</Link>
            </Button>
          </>
        ) : state.error ? (
          <>
            <p role="alert" className="text-sm text-danger">
              {state.error} You can send a new one from Help, under Your account.
            </p>
            <Button asChild variant="outline" className="w-full">
              <Link to="/login">Go to sign-in</Link>
            </Button>
          </>
        ) : (
          <p className="flex items-center gap-2 text-sm text-fg-2">
            <Loader2 className="size-4 animate-spin" aria-hidden /> Confirming…
          </p>
        )}
      </div>
    </Frame>
  );
}
