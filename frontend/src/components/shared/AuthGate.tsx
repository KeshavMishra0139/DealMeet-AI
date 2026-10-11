import { useQueryClient } from "@tanstack/react-query";
import { LogOut } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { ErrorState } from "@/components/shared/Bits";
import { Wordmark } from "@/components/shared/Wordmark";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { forgetRole, pinnedPersona, useSession, type Me, type Role } from "@/lib/session";

const HOME: Record<string, string> = { creator: "/creator", brand: "/brand", admin: "/admin" };
const ONBOARDING: Record<Role, string> = { creator: "/creator/onboarding", brand: "/brand/onboarding" };

/** A safe in-app path to return to after signing in (never another site). */
export function safeNext(next: string | null): string | null {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : null;
}

function Waiting() {
  return <div className="min-h-dvh" aria-busy="true" aria-label="Checking your sign-in" />;
}

/**
 * Renders `children` only for a signed-in account of `role` with a profile. Everyone else
 * is sent to sign in, to onboarding, or told which side their account belongs to.
 * The server checks every request anyway; this only decides what to show.
 */
export function RequireSession({ role, needsProfile = true, children }: { role: Role; needsProfile?: boolean; children: ReactNode }) {
  const session = useSession(role);
  const location = useLocation();
  if (session.isPending) return <Waiting />;
  if (session.isError)
    return (
      <div className="mx-auto max-w-md p-6">
        <ErrorState error={session.error} onRetry={() => session.refetch()} />
      </div>
    );
  const me = session.data;
  if (!me) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?role=${role}&next=${next}`} replace />;
  }
  if (me.user.role !== role) return <WrongSide me={me} wanted={role} />;
  const hasProfile = role === "creator" ? !!me.user.creator_id && !!me.profile : !!me.user.brand_id && !!me.profile;
  if (needsProfile && !hasProfile) return <Navigate to={ONBOARDING[role]} replace />;
  if (!needsProfile && hasProfile) return <Navigate to={HOME[role]} replace />;
  return <>{children}</>;
}

function WrongSide({ me, wanted }: { me: Me; wanted: Role }) {
  const signOut = useSignOut(wanted);
  const label = (r: string) => (r === "creator" ? "a creator" : r === "brand" ? "a brand" : "an admin");
  return (
    <div className="mx-auto flex min-h-dvh max-w-md flex-col justify-center gap-5 px-5">
      <Wordmark />
      <h1 className="font-display text-2xl font-semibold">This part is for {label(wanted)} account</h1>
      <p className="text-fg-2">
        You're signed in as {me.user.name ?? me.user.email}, {label(me.user.role)} account. Each account is either a creator or a brand.
      </p>
      <div className="flex flex-wrap gap-2">
        <Button asChild variant="primary">
          <Link to={HOME[me.user.role] ?? "/"}>Go to your {me.user.role === "creator" ? "Creator Studio" : me.user.role === "brand" ? "Brand Console" : "admin console"}</Link>
        </Button>
        <Button variant="outline" onClick={signOut.run} loading={signOut.busy}>
          Sign out
        </Button>
      </div>
    </div>
  );
}

/** Signs this side out on the server, forgets its token and goes to the sign-in page. */
export function useSignOut(role: Role) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  return {
    busy,
    run: async () => {
      setBusy(true);
      try {
        await api("/auth/logout", { method: "POST", json: {}, role });
      } catch {
        /* signing out locally still works if the server can't be reached */
      }
      forgetRole(role);
      qc.removeQueries();
      setBusy(false);
      navigate(`/login?role=${role}`, { replace: true });
    },
  };
}

export function SignOutButton({ role, onDone, className, size = "md" }: { role: Role; onDone?: () => void; className?: string; size?: "sm" | "md" }) {
  const signOut = useSignOut(role);
  // A demo frame pinned to a persona has nothing to sign out of.
  if (pinnedPersona(role)) return null;
  return (
    <Button
      variant="ghost"
      size={size}
      className={className}
      loading={signOut.busy}
      onClick={async () => {
        onDone?.();
        await signOut.run();
      }}
    >
      {!signOut.busy && <LogOut aria-hidden />} Sign out
    </Button>
  );
}
