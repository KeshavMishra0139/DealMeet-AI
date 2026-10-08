import { Link } from "react-router-dom";
import { Wordmark } from "@/components/shared/Wordmark";
import { Button } from "@/components/ui/button";
import { useTheme } from "@/lib/theme";

export default function NotFound() {
  useTheme("creator");
  return (
    <div className="theme-creator grain relative grid min-h-dvh place-items-center px-6">
      <div className="aurora" aria-hidden>
        <span />
      </div>
      <main id="main" className="relative z-10 text-center">
        <Wordmark className="justify-center" />
        <h1 className="mt-8 font-display text-3xl font-semibold">This page isn't here</h1>
        <p className="mt-2 text-fg-2">The link may be old, or the profile may have been made private.</p>
        <Button asChild variant="primary" className="mt-6">
          <Link to="/">Go to the start</Link>
        </Button>
      </main>
    </div>
  );
}
