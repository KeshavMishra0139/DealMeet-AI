import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, Copy, Download, ExternalLink, Globe, History, Link2, Save, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { ErrorState, SectionTitle } from "@/components/shared/Bits";
import { KitCard } from "@/components/shared/KitCard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { FieldHint, Input, Label, Segmented, Skeleton, Switch, Textarea } from "@/components/ui/form";
import { useI18n } from "@/i18n";
import { api, post, put, del } from "@/lib/api";
import { inr, shortDate } from "@/lib/format";
import type { Kit as KitData, KitLang, KitSection, KitVersion } from "@/lib/kit-types";
import { useCreatorId } from "@/lib/session";

const SECTIONS: [KitSection, string][] = [
  ["stats", "Reach and engagement"],
  ["formats", "What performs best"],
  ["rates", "Rates"],
  ["audience", "Audience"],
  ["trust", "Trust and brand safety"],
];

export default function Kit() {
  const id = useCreatorId();
  const { t, lang: appLang } = useI18n();
  const [lang, setLang] = useState<KitLang>(appLang === "hi" ? "hi" : "en");
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["kit", id, lang], queryFn: () => api<KitData>(`/creators/${id}/kit?lang=${lang}`) });
  const save = useMutation({
    mutationFn: (pub: NonNullable<KitData["public"]>) => post<KitData>(`/creators/${id}/kit?lang=${lang}`, pub),
    onSuccess: (k) => {
      qc.setQueryData(["kit", id, lang], k);
      void qc.invalidateQueries({ queryKey: ["kit", id] });
    },
  });
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data) return <Skeleton className="h-[600px] rounded-[28px]" />;
  const k = q.data;
  const pub = k.public ?? { stats: true, demographics: false, rates: true };
  const url = `${window.location.origin}${k.path}`;

  return (
    <div>
      <h1 className="font-display text-[28px] font-semibold tracking-tight sm:text-[34px]">{t("kit.title")}</h1>
      <p className="mt-1 text-[15px] text-fg-2">The live view is rebuilt from your current numbers. Save a version to keep a copy that never changes.</p>

      <div className="mt-6 grid gap-4 lg:grid-cols-[1.5fr_1fr]">
        <div>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <p className="flex items-center gap-1.5 text-sm font-medium">
              <Globe className="size-4 text-accent" aria-hidden /> Live view
            </p>
            <Segmented
              label="Media kit language"
              size="sm"
              value={lang}
              onChange={setLang}
              options={[
                { value: "en", label: "English" },
                { value: "hi", label: "हिंदी" },
              ]}
            />
          </div>
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
                <a href={`/api/creators/${id}/kit.pdf?lang=${lang}`} target="_blank" rel="noreferrer">
                  <Download aria-hidden /> {lang === "hi" ? "Hindi PDF" : "Media kit PDF"}
                </a>
              </Button>
            </div>
            <p className="mt-3 text-xs text-muted">
              Brands book you from this page. Their payment is held in escrow before you post.
              {k.from_rate != null && ` ${k.rates_kind === "your_rate" ? "Your rates" : "Estimated rates"} start at ${inr(k.from_rate)}.`}
            </p>
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
            <p className="mt-2 text-xs text-muted">These apply to the live view and to any saved version you show. Change brand access in Privacy.</p>
            {k.has_simulated && (
              <Badge size="sm" variant="warn" className="mt-3">
                Some values are sample data for this demo profile
              </Badge>
            )}
          </section>
        </div>
      </div>

      <Versions creatorId={id} kit={k} lang={lang} />
    </div>
  );
}

function Versions({ creatorId, kit, lang }: { creatorId: string; kit: KitData; lang: KitLang }) {
  const qc = useQueryClient();
  const list = useQuery({
    queryKey: ["kit-versions", creatorId],
    queryFn: () => api<{ versions: KitVersion[]; public_version: string | null; max: number }>(`/creators/${creatorId}/kit/versions`),
  });
  const [headline, setHeadline] = useState<string | null>(null);
  const [bio, setBio] = useState<string | null>(null);
  const [sections, setSections] = useState<Record<KitSection, boolean>>({ stats: true, formats: true, audience: true, rates: true, trust: true });
  const h = headline ?? kit.copy.headline;
  const b = bio ?? kit.copy.bio;
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["kit-versions", creatorId] });
    void qc.invalidateQueries({ queryKey: ["kit", creatorId] });
  };
  const create = useMutation({
    mutationFn: () => post<KitVersion & { created: boolean }>(`/creators/${creatorId}/kit/versions`, { headline: h, bio: b, sections, lang }),
    onSuccess: (v) => {
      refresh();
      if (v.created) toast.success(`Version ${v.number} saved`, { description: "It keeps this content and its own PDF, and never changes." });
      else toast(`This is the same as version ${v.number}`, { description: "Nothing new was saved." });
    },
    onError: (e) => toast.error((e as Error).message),
  });
  const show = useMutation({
    mutationFn: (versionId: string | null) => put(`/creators/${creatorId}/kit/public-view`, { version_id: versionId }),
    onSuccess: (_, versionId) => {
      refresh();
      toast.success(versionId ? "Your public page now shows this version" : "Your public page now shows the live view");
    },
    onError: (e) => toast.error((e as Error).message),
  });
  const remove = useMutation({
    mutationFn: (versionId: string) => del(`/creators/${creatorId}/kit/versions/${versionId}`),
    onSuccess: refresh,
    onError: (e) => toast.error((e as Error).message),
  });
  const versions = list.data?.versions ?? [];
  const live = !list.data?.public_version;

  return (
    <section aria-labelledby="versions" className="mt-8 grid gap-4 lg:grid-cols-[1fr_1fr]">
      <div className="card-surface rounded-[var(--radius-card)] p-5">
        <SectionTitle id="versions" eyebrow="Saved versions" title="Edit and save a version" />
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            create.mutate();
          }}
        >
          <div>
            <Label htmlFor="kv-headline">Headline</Label>
            <Input id="kv-headline" value={h} onChange={(e) => setHeadline(e.target.value)} minLength={3} maxLength={120} required />
          </div>
          <div>
            <Label htmlFor="kv-bio">Bio</Label>
            <Textarea id="kv-bio" value={b} onChange={(e) => setBio(e.target.value)} maxLength={420} />
            <FieldHint>Describe your content and audience. Text that promises results can't be saved.</FieldHint>
          </div>
          <fieldset>
            <legend className="mb-1 text-[13px] font-medium text-fg-2">Sections to show</legend>
            {SECTIONS.map(([key, label]) => (
              <label key={key} className="flex items-center justify-between gap-4 py-1.5 text-sm">
                {label}
                <Switch checked={sections[key]} onCheckedChange={(v) => setSections((s) => ({ ...s, [key]: v }))} aria-label={`Include ${label.toLowerCase()}`} />
              </label>
            ))}
            <FieldHint>Sections your sharing settings hide stay hidden on your public page.</FieldHint>
          </fieldset>
          <Button type="submit" variant="primary" loading={create.isPending}>
            {!create.isPending && <Save aria-hidden />} Save as version ({lang === "hi" ? "Hindi" : "English"})
          </Button>
        </form>
      </div>

      <div className="card-surface rounded-[var(--radius-card)] p-5">
        <SectionTitle id="version-list" eyebrow="History" title="Your versions" />
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2 rounded-xl bg-surface-2 px-3 py-2.5 text-sm">
          <span>
            Public page shows: <span className="font-medium">{live ? "Live view" : `Version ${versions.find((v) => v.published)?.number ?? ""}`}</span>
          </span>
          {!live && (
            <Button size="sm" variant="ghost" loading={show.isPending} onClick={() => show.mutate(null)}>
              Show live view
            </Button>
          )}
        </div>
        {list.isError && <ErrorState error={list.error} onRetry={() => list.refetch()} />}
        {list.data && versions.length === 0 && <p className="text-sm text-muted">No saved versions yet. Your public page shows the live view.</p>}
        <ol className="divide-y divide-line">
          {versions.map((v) => (
            <li key={v.id} className="flex flex-wrap items-start gap-x-3 gap-y-2 py-3">
              <History className="mt-0.5 size-4 shrink-0 text-muted" aria-hidden />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium">
                  Version {v.number} <span className="font-normal text-muted">· {v.lang === "hi" ? "Hindi" : "English"} · saved {shortDate(v.created_at, true)}</span>
                </p>
                <p className="truncate text-[13px] text-fg-2">{v.headline}</p>
                {v.published && (
                  <Badge size="sm" variant="success" className="mt-1">
                    On your public page
                  </Badge>
                )}
              </div>
              <div className="flex flex-wrap gap-1.5">
                <Button asChild size="sm" variant="outline">
                  <a href={`/api/creators/${creatorId}/kit/versions/${v.id}/pdf`} target="_blank" rel="noreferrer" aria-label={`PDF of version ${v.number}`}>
                    <Download aria-hidden /> PDF
                  </a>
                </Button>
                {!v.published && (
                  <Button size="sm" variant="outline" onClick={() => show.mutate(v.id)} aria-label={`Show version ${v.number} on your public page`}>
                    Show
                  </Button>
                )}
                {!v.published && (
                  <Button size="sm" variant="ghost" onClick={() => remove.mutate(v.id)} aria-label={`Delete version ${v.number}`}>
                    <Trash2 aria-hidden />
                  </Button>
                )}
              </div>
            </li>
          ))}
        </ol>
        {list.data && <p className="mt-2 text-xs text-muted">Up to {list.data.max} versions. Each keeps the content and PDF it was saved with.</p>}
      </div>
    </section>
  );
}
