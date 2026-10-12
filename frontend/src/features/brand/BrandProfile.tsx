import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BadgeCheck, Save } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Avatar, ErrorState } from "@/components/shared/Bits";
import { SourceBadge } from "@/components/shared/SourceBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { FieldHint, Input, Label, Skeleton, Textarea } from "@/components/ui/form";
import { api } from "@/lib/api";
import { inr } from "@/lib/format";
import { useBrandId } from "@/lib/session";
import { useBrand } from "./BrandShell";

interface Org {
  id: string;
  name: string;
  slug: string | null;
  category: string;
  website: string | null;
  description: string;
  hue: number;
  verified: boolean;
  source: string | null;
  contact: { name: string | null; email: string | null; phone: string | null };
  public_handles: { instagram?: string; youtube?: string };
  updated_at: string | null;
}

export default function BrandProfile() {
  const id = useBrandId();
  const q = useBrand();
  const org = useQuery({ queryKey: ["brand-profile", id], queryFn: () => api<Org>(`/brands/${id}/profile`) });
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (org.isError) return <ErrorState error={org.error} onRetry={() => org.refetch()} />;
  if (!q.data || !org.data) return <Skeleton className="h-64 rounded-xl" />;
  const b = q.data;
  const rows: [string, React.ReactNode][] = [
    ["Goal", b.goal ?? "—"],
    ["Monthly creator budget", b.budget_monthly ? inr(b.budget_monthly) : "—"],
    ["Target ages", b.target.ages.join(", ") || "Any"],
    ["Gender", b.target.gender === "any" ? "Everyone" : b.target.gender === "female" ? "Mostly women" : "Mostly men"],
    ["Languages", b.target.languages.join(", ")],
    ["Regions", b.target.regions.join(", ")],
    ["Priority cities", b.target.cities.join(", ") || "Pan-India"],
  ];
  return (
    <div className="max-w-2xl">
      <div className="flex items-center gap-3.5">
        <Avatar name={org.data.name} hue={org.data.hue} size={48} className="rounded-xl" />
        <div>
          <h1 className="flex items-center gap-2 font-display text-2xl font-semibold tracking-tight">
            {org.data.name} {org.data.verified && <BadgeCheck className="size-5 text-accent" aria-label="Verified" />}
          </h1>
          <p className="flex flex-wrap items-center gap-2 text-sm text-muted">
            {org.data.category} <SourceBadge source={org.data.source} />
            {!org.data.verified && <Badge size="sm">Not verified</Badge>}
          </p>
        </div>
      </div>

      <OrgForm key={org.data.updated_at ?? "x"} org={org.data} />

      <h2 className="mt-8 font-display text-lg font-semibold">Who you want to reach</h2>
      <dl className="card-surface mt-3 divide-y divide-line rounded-xl">
        {rows.map(([k, v]) => (
          <div key={k} className="grid grid-cols-[150px_1fr] gap-3 px-4 py-3 text-sm sm:grid-cols-[180px_1fr]">
            <dt className="text-muted">{k}</dt>
            <dd>{v}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-4 text-xs text-muted">
        Matching uses this target to score audience fit. Creators share data with you only by consent; every profile you open is logged in their ledger.
      </p>
    </div>
  );
}

function OrgForm({ org }: { org: Org }) {
  const qc = useQueryClient();
  const [f, setF] = useState({
    name: org.name,
    slug: org.slug ?? "",
    category: org.category,
    website: org.website ?? "",
    description: org.description,
    contact_name: org.contact.name ?? "",
    contact_email: org.contact.email ?? "",
    contact_phone: org.contact.phone ?? "",
    instagram: org.public_handles.instagram ?? "",
    youtube: org.public_handles.youtube ?? "",
  });
  const set = (k: keyof typeof f, v: string) => setF((p) => ({ ...p, [k]: v }));
  const save = useMutation({
    mutationFn: () =>
      api<Org>(`/brands/${org.id}/profile`, {
        method: "PATCH",
        json: {
          name: f.name,
          slug: f.slug,
          category: f.category,
          website: f.website.trim() || null,
          description: f.description,
          contact: { name: f.contact_name || null, email: f.contact_email || null, phone: f.contact_phone || null },
          public_handles: { instagram: f.instagram || null, youtube: f.youtube || null },
        },
      }),
    onSuccess: (o) => {
      qc.setQueryData(["brand-profile", org.id], o);
      void qc.invalidateQueries({ queryKey: ["brand", org.id] });
      toast.success("Organisation profile saved");
    },
    onError: (e) => toast.error((e as Error).message),
  });
  return (
    <form
      className="card-surface mt-6 space-y-4 rounded-xl p-5"
      aria-label="Organisation profile"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <Label htmlFor="bp-name">Brand name</Label>
          <Input id="bp-name" value={f.name} onChange={(e) => set("name", e.target.value)} minLength={2} maxLength={60} required />
        </div>
        <div>
          <Label htmlFor="bp-category">Category</Label>
          <Input id="bp-category" value={f.category} onChange={(e) => set("category", e.target.value)} minLength={2} maxLength={60} required />
        </div>
      </div>
      <div>
        <Label htmlFor="bp-slug">Address on DealMeet</Label>
        <Input id="bp-slug" value={f.slug} onChange={(e) => set("slug", e.target.value.toLowerCase())} minLength={3} maxLength={40} pattern="[a-z0-9-]+" />
        <FieldHint>dealmeet.ai/brands/{f.slug || "your-brand"} · lowercase letters, numbers and hyphens.</FieldHint>
      </div>
      <div>
        <Label htmlFor="bp-site">Website</Label>
        <Input id="bp-site" type="url" value={f.website} onChange={(e) => set("website", e.target.value)} placeholder="https://" maxLength={200} />
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <Label htmlFor="bp-ig">Instagram handle</Label>
          <Input id="bp-ig" value={f.instagram} onChange={(e) => set("instagram", e.target.value)} placeholder="@yourbrand" maxLength={41} />
        </div>
        <div>
          <Label htmlFor="bp-yt">YouTube handle</Label>
          <Input id="bp-yt" value={f.youtube} onChange={(e) => set("youtube", e.target.value)} placeholder="@yourbrand" maxLength={41} />
        </div>
        <FieldHint className="sm:col-span-2">Fan Proof looks for these handles and #{f.name.toLowerCase().replace(/[^a-z0-9]/g, "")} in creators' synced posts.</FieldHint>
      </div>
      <div>
        <Label htmlFor="bp-desc">About</Label>
        <Textarea id="bp-desc" value={f.description} onChange={(e) => set("description", e.target.value)} maxLength={400} />
      </div>
      <fieldset className="grid gap-4 sm:grid-cols-3">
        <legend className="mb-1 text-[13px] font-medium text-fg-2">Contact (only you see this)</legend>
        <div>
          <Label htmlFor="bp-cname">Name</Label>
          <Input id="bp-cname" value={f.contact_name} onChange={(e) => set("contact_name", e.target.value)} maxLength={60} />
        </div>
        <div>
          <Label htmlFor="bp-cemail">Email</Label>
          <Input id="bp-cemail" type="email" value={f.contact_email} onChange={(e) => set("contact_email", e.target.value)} maxLength={120} />
        </div>
        <div>
          <Label htmlFor="bp-cphone">Phone</Label>
          <Input id="bp-cphone" type="tel" value={f.contact_phone} onChange={(e) => set("contact_phone", e.target.value)} maxLength={20} />
        </div>
      </fieldset>
      <div className="flex justify-end">
        <Button type="submit" variant="primary" loading={save.isPending}>
          {!save.isPending && <Save aria-hidden />} Save profile
        </Button>
      </div>
    </form>
  );
}
