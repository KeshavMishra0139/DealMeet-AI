import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, Heart, Search, Trash2 } from "lucide-react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { ErrorState } from "@/components/shared/Bits";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton, Switch } from "@/components/ui/form";
import { useI18n } from "@/i18n";
import { api, del, post, put } from "@/lib/api";
import { shortDate } from "@/lib/format";
import { useCreatorId } from "@/lib/session";
import { BrandTile, type BrandCard } from "@/features/public/Brands";

interface Dream {
  items: (BrandCard & { saved_at: string | null; show_name: boolean })[];
  notifications: { id: string; brand_id: string; brand_name: string; listing_id: string; title: string; listing_type: string; at: string; read: boolean }[];
  unread: number;
}

/** Brands the creator wants to work with, and news when they open a campaign. */
export default function DreamBrands() {
  const id = useCreatorId();
  const { t } = useI18n();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["dream", id], queryFn: () => api<Dream>(`/creators/${id}/dream-brands`) });
  const refresh = () => void qc.invalidateQueries({ queryKey: ["dream", id] });
  const share = useMutation({
    mutationFn: ({ brandId, show }: { brandId: string; show: boolean }) => put(`/creators/${id}/dream-brands/${brandId}`, { show_name: show }),
    onSuccess: refresh,
    onError: (e) => toast.error((e as Error).message),
  });
  const remove = useMutation({
    mutationFn: (brandId: string) => del(`/creators/${id}/dream-brands/${brandId}`),
    onSuccess: refresh,
    onError: (e) => toast.error((e as Error).message),
  });
  const read = useMutation({ mutationFn: () => post(`/creators/${id}/dream-brands/read`), onSuccess: refresh });

  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data) return <Skeleton className="h-96 rounded-[28px]" />;
  const d = q.data;

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-[28px] font-semibold tracking-tight sm:text-[34px]">{t("nav.dream")}</h1>
          <p className="mt-1 text-[15px] text-fg-2">Brands you'd love to work with. Each brand sees only how many creators saved it, never who, unless you allow it.</p>
        </div>
        <Button asChild variant="primary" size="sm">
          <Link to="/brands">
            <Search aria-hidden /> Browse brands
          </Link>
        </Button>
      </div>

      {d.notifications.length > 0 && (
        <section aria-labelledby="news" className="card-surface mt-6 rounded-[var(--radius-card)] p-5">
          <div className="flex items-center justify-between gap-2">
            <h2 id="news" className="flex items-center gap-1.5 text-sm font-semibold">
              <Bell className="size-4 text-accent" aria-hidden /> News from your Dream Brands {d.unread > 0 && <Badge size="sm" variant="accent">{d.unread} new</Badge>}
            </h2>
            {d.unread > 0 && (
              <Button size="sm" variant="ghost" onClick={() => read.mutate()}>
                Mark all read
              </Button>
            )}
          </div>
          <ul className="mt-2 divide-y divide-line">
            {d.notifications.map((n) => (
              <li key={n.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5 text-sm">
                <span>
                  <span className="font-medium">{n.brand_name}</span> opened {n.listing_type === "collective" ? "a collective" : "a campaign"}: {n.title}
                  {!n.read && <span className="sr-only"> (new)</span>}
                </span>
                <span className="flex items-center gap-2">
                  <span className="text-xs text-muted">{shortDate(n.at)}</span>
                  <Button asChild size="sm" variant="outline">
                    <Link to="/creator/opportunities">See it</Link>
                  </Button>
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {d.items.length === 0 ? (
        <div className="card-surface mt-6 rounded-[var(--radius-card)] p-6 text-center">
          <Heart className="mx-auto size-6 text-accent" aria-hidden />
          <p className="mt-2 text-sm text-fg-2">No Dream Brands yet. Browse brands and save the ones you'd love to work with.</p>
        </div>
      ) : (
        <ul className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {d.items.map((b) => (
            <li key={b.id} className="flex flex-col gap-2">
              <BrandTile b={b} />
              <div className="flex items-center justify-between gap-2 px-1">
                <label className="flex items-center gap-2 text-xs text-fg-2">
                  <Switch checked={b.show_name} onCheckedChange={(v) => share.mutate({ brandId: b.id, show: v })} aria-label={`Let ${b.name} see my name`} />
                  Let them see my name
                </label>
                <Button size="sm" variant="ghost" onClick={() => remove.mutate(b.id)} aria-label={`Remove ${b.name} from your Dream Brands`}>
                  <Trash2 aria-hidden />
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
