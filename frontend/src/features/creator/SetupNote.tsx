// After a creator is set up from YouTube or Instagram (no form), Home says so once: what was
// filled in, and the one thing the account couldn't tell us (the city) with a link to add it.
import { Sparkles, X } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { useCreator } from "./CreatorShell";

const KEY = (id: string) => `dm-setup-note:${id}`;

function seen(id: string) {
  try {
    return localStorage.getItem(KEY(id)) === "1";
  } catch {
    return false;
  }
}

export function SetupNote({ className }: { className?: string }) {
  const c = useCreator().data;
  const [hidden, setHidden] = useState(false);
  const setup = c?.auto_setup;
  if (!c || !setup || hidden || seen(c.id)) return null;
  const from = setup.source === "youtube" ? "YouTube channel" : "Instagram";
  const needsCity = !c.city;
  const close = () => {
    try {
      localStorage.setItem(KEY(c.id), "1");
    } catch {
      /* private window: it just shows again next time */
    }
    setHidden(true);
  };
  return (
    <section aria-label="Set up from your account" className={`card-surface relative flex flex-wrap items-center gap-3 rounded-[var(--radius-card)] p-4 ${className ?? ""}`}>
      <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-signature text-white">
        <Sparkles className="size-4" aria-hidden />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold">Set up from your {from}</p>
        <p className="mt-0.5 text-[13px] leading-snug text-fg-2">
          {c.niche_label} · {c.language_labels.join(", ")} · {(c.formats ?? []).join(" and ")}
          {setup.review.includes("niche") ? ". We weren't sure of your niche: check it" : ""}
          {needsCity ? ". Add your city so regional brands can find you." : "."}
        </p>
      </div>
      <Button asChild size="sm" variant={needsCity ? "primary" : "outline"}>
        <Link to="/creator/profile" onClick={close}>
          {needsCity ? "Add your city" : "Review profile"}
        </Link>
      </Button>
      <button type="button" onClick={close} aria-label="Dismiss" className="grid size-8 place-items-center rounded-lg text-muted hover:bg-surface-2 hover:text-fg">
        <X className="size-4" aria-hidden />
      </button>
    </section>
  );
}
