// What happens once the server has started a session, whichever way the person signed in
// (password, Google or phone, Instagram, YouTube).
import { useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { forgetAllTokens, type SessionUser } from "@/lib/session";

export function homeFor(user: SessionUser) {
  if (user.role === "admin") return "/admin";
  if (user.role === "brand") return user.brand_id ? "/brand" : "/brand/onboarding";
  return user.creator_id ? "/creator" : "/creator/onboarding";
}

/** Where to go after signing in: back where you came from if it's your side of the app. */
export function destination(user: SessionUser, next: string | null) {
  const home = homeFor(user);
  const side = home.split("/").slice(0, 2).join("/");
  return next && next.startsWith(side) ? next : home;
}

/** Re-reads the session and goes to the right page. A note from the server is shown once. */
export function useFinishSignIn() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  return async (user: SessionUser, next: string | null, note?: string) => {
    // The cookie session now speaks for this browser; demo tokens would shadow it.
    forgetAllTokens();
    await qc.invalidateQueries({ queryKey: ["session"] });
    if (note) toast.info(note);
    navigate(destination(user, next), { replace: true });
  };
}
