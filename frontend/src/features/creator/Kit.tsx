import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, Copy, Download, ExternalLink, Link2 } from "lucide-react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { ErrorState, SectionTitle } from "@/components/shared/Bits";
import { KitCard } from "@/components/shared/KitCard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton, Switch } from "@/components/ui/form";
import { useI18n } from "@/i18n";
import { api, post } from "@/lib/api";
import { inr } from "@/lib/format";
import type { Kit as KitData } from "@/lib/kit-types";
import { useCreatorId } from "@/lib/session";

export default function Kit() {
  const id = useCreatorId();
  const { t } = useI18n();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["kit", id], queryFn: () => api<KitData>(`/creators/${id}/kit`) });
  const save = useMutation({
    mutationFn: (pub: NonNullable<KitData["public"]>) => post<KitData>(`/creators/${id}/kit`, pub),
    onSuccess: (k) => qc.setQueryData(["kit", id], k),
  });
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data) return <Skeleton className="h-[600px] rounded-[28px]" />;
  const k = q.data;
  const pub = k.public ?? { stats: true, demographics: false, rates: true };
  const url = `${window.location.origin}${k.path}`;

  return (
    <div>
      <h1 className="font-display text-[28px] font-semibold tracking-tight sm:text-[34px]">{t("kit.title")}</h1>
      <p className="mt-1 text-[15px] text-fg-2">Built from your connected numbers. Share the link, or send the PDF.</p>

      <div className="mt-6 grid gap-4 lg:grid-cols-[1.5fr_1fr]">
        <div>
          <KitCard kit={k} />
          <p className="mt-2 flex items-center gap-1.5 text-xs text-muted">
            <Bot className="size-3.5" aria-hidden /> {k.copy_source === "template" ? "Copy written from your numbers (offline template)." : "Copy drafted by AI from your numbers."}
          </p>
        </div>

        <div className="space-y-4">
          <section aria-labelledby="share" className="card-surface rounded-[var(--radius-card)] p-5">
            <SectionTitle id="share" eyebrow="Link-in-bio" title="Your JodiDar page" />
            <div className="flex items-center gap-2 rounded-xl border border-line bg-surface-2 px-3 py-2.5 text-sm">
              <Link2 className="size-4 shrink-0 text-accent" aria-hidden />
              <span className="truncate">{`${window.location.host}${k.path}`}</span>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button
                size="sm"
                variant="primary"
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(url);
                    toast.success("Link copied");
                  } catch {
                    toast(url);
                  }
                }}
              >
                <Copy aria-hidden /> Copy link
              </Button>
              <Button asChild size="sm" variant="outline">
                <Link to={k.path} target="_blank">
                  <ExternalLink aria-hidden /> Open page
                </Link>
              </Button>
              <Button asChild size="sm" variant="outline">
                <a href={`/api/creators/${id}/kit.pdf`} target="_blank" rel="noreferrer">
                  <Download aria-hidden /> Media kit PDF
                </a>
              </Button>
            </div>
            <p className="mt-3 text-xs text-muted">Brands book you from this page. Their payment is held in escrow before you post.{k.from_rate != null && ` Rates start at ${inr(k.from_rate)}.`}</p>
          </section>

          <section aria-labelledby="pub" className="card-surface rounded-[var(--radius-card)] p-5">
            <SectionTitle id="pub" eyebrow="Public" title="What your page shows" />
            {(
              [
                ["stats", "Reach and engagement"],
                ["demographics", "Audience demographics"],
                ["rates", "Rate card"],
              ] as const
            ).map(([key, label]) => (
              <label key={key} className="flex items-center justify-between gap-4 py-2 text-sm">
                {label}
                <Switch checked={pub[key]} onCheckedChange={(v) => save.mutate({ ...pub, [key]: v })} aria-label={`Show ${label.toLowerCase()} publicly`} />
              </label>
            ))}
            <p className="mt-2 text-xs text-muted">Separate from what each brand sees in the marketplace. Change brand access in Privacy.</p>
            {k.has_simulated && (
              <Badge size="sm" variant="warn" className="mt-3">
                Some values are simulated for this demo profile
              </Badge>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
