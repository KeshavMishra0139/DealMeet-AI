// Where Instagram's login lands (via the API's callback). The address carries a one-time
// code; posting it from this page starts the session on the web app's own origin.
import { Loader2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Wordmark } from "@/components/shared/Wordmark";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { SessionUser } from "@/lib/session";
import { useTheme } from "@/lib/theme";
import { useFinishSignIn } from "./signin";

export default function LoginComplete() {
  useTheme("creator");
  const [params] = useSearchParams();
  const code = params.get("code");
  const finish = useFinishSignIn();
  const started = useRef(false);
  const [error, setError] = useState(code ? "" : "This sign-in link is missing its code. Sign in again.");

  useEffect(() => {
    // The code works once, so it's sent once (React's development double-run included).
    if (!code || started.current) return;
    started.current = true;
    window.history.replaceState(window.history.state, "", "/login/complete"); // keep it out of history
    api<{ user: SessionUser; next?: string | null; note?: string }>("/auth/oauth/complete", { method: "POST", json: { code }, role: null })
      .then((r) => finish(r.user, r.next ?? null, r.note))
      .catch((e: Error) => setError(e.message));
  }, [code, finish]);

  return (
    <div className="theme-creator relative grid min-h-dvh place-items-center px-4">
      <main id="main" className="w-full max-w-sm text-center">
        <Wordmark />
        {error ? (
          <div className="mt-8 space-y-4">
            <p role="alert" className="text-sm text-danger">
              {error}
            </p>
            <Button asChild variant="primary" className="w-full">
              <Link to="/login?role=creator">Back to sign-in</Link>
            </Button>
          </div>
        ) : (
          <p className="mt-8 flex items-center justify-center gap-2 text-sm text-fg-2" aria-live="polite">
            <Loader2 className="size-4 animate-spin" aria-hidden /> Signing you in…
          </p>
        )}
      </main>
    </div>
  );
}
