import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, ArrowRight, Calculator, Save, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { ErrorState } from "@/components/shared/Bits";
import { SourceBadge } from "@/components/shared/SourceBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { FieldHint, Input, Label, Select } from "@/components/ui/form";
import { api, del, put } from "@/lib/api";
import { inr, inrRange, shortDate } from "@/lib/format";
import { cn } from "@/lib/utils";

type Format = "reel" | "story" | "carousel" | "live" | "short" | "youtube_video";

interface Metric {
  key: string;
  label: string;
  value: string;
  source: string;
  note: string | null;
}
interface Missing {
  key: string;
  label: string;
  effect: string;
  fix: string;
  path: string;
}
interface EstimateOut {
  format: Format;
  format_label: string;
  deliverables: string;
  terms: string[];
  enough_data: boolean;
  range: { low: number; high: number } | null;
  data_label: string | null;
  data_source: string | null;
  metrics: Metric[];
  missing: Missing[];
  assumptions: string[];
  confidence: string | null;
}
interface Card {
  format: Format;
  format_label: string;
  deliverables: string;
  terms: string[];
  count: number;
  usage_rights_days: number;
  exclusivity_days: number;
  amount: number;
  note: string | null;
  saved_at: string;
  estimate_now: { range: { low: number; high: number } | null; data_label: string | null; data_source: string | null; enough_data: boolean };
}
interface RatesOut {
  cards: Card[];
  formats: { key: Format; label: string; estimate_available: boolean; reason: string | null }[];
}

const DAYS = [0, 15, 30, 60, 90];

/** The pricing form and the creator's saved rate per format. */
export function RateCards({ creatorId }: { creatorId: string }) {
  const qc = useQueryClient();
  const rates = useQuery({ queryKey: ["rates", creatorId], queryFn: () => api<RatesOut>(`/creators/${creatorId}/rates`) });
  const [picked, setFormat] = useState<Format | null>(null);
  // The creator's own platform's first format until they pick one (a Short on YouTube).
  const format: Format = picked ?? rates.data?.formats[0]?.key ?? "reel";
  const [count, setCount] = useState(1);
  const [usage, setUsage] = useState(0);
  const [excl, setExcl] = useState(0);
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const [amountErr, setAmountErr] = useState("");
  const params = new URLSearchParams({ format, count: String(count), usage_rights_days: String(usage), exclusivity_days: String(excl) });
  const est = useQuery({
    queryKey: ["estimate", creatorId, format, count, usage, excl],
    queryFn: () => api<EstimateOut>(`/creators/${creatorId}/pricing/estimate?${params}`),
    placeholderData: keepPreviousData,
    // Waits for the creator's own first format rather than estimating a reel for a YouTube creator.
    enabled: !!rates.data || picked !== null,
  });
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["rates", creatorId] });
    void qc.invalidateQueries({ queryKey: ["kit", creatorId] });
    void qc.invalidateQueries({ queryKey: ["money", creatorId] });
  };
  const save = useMutation({
    mutationFn: (amt: number) => put<Card>(`/creators/${creatorId}/rates/${format}`, { amount: amt, count, usage_rights_days: usage, exclusivity_days: excl, note: note.trim() || null }),
    onSuccess: (c) => {
      refresh();
      setAmount("");
      setNote("");
      toast.success(`Your rate for ${c.deliverables} saved`, { description: "It shows on your media kit when rates are public." });
    },
    onError: (e) => toast.error((e as Error).message),
  });
  const remove = useMutation({
    mutationFn: (f: Format) => del(`/creators/${creatorId}/rates/${f}`),
    onSuccess: refresh,
    onError: (e) => toast.error((e as Error).message),
  });
  const e = est.data;
  const edit = (c: Card) => {
    setFormat(c.format);
    setCount(c.count);
    setUsage(c.usage_rights_days);
    setExcl(c.exclusivity_days);
    setAmount(String(c.amount));
    setNote(c.note ?? "");
  };

  return (
    <section aria-labelledby="rates" className="mt-8">
      <h2 id="rates" className="mb-1 font-display text-lg font-semibold">
        Your rates
      </h2>
      <p className="mb-3 text-[13px] text-fg-2">Set your own price per format. The estimate next to it uses only the numbers you have.</p>

      {rates.isError && <ErrorState error={rates.error} onRetry={() => rates.refetch()} />}
      {rates.data && rates.data.cards.length > 0 && (
        <ul className="mb-4 grid gap-3 sm:grid-cols-2">
          {rates.data.cards.map((c) => (
            <li key={c.format} className="card-surface rounded-[var(--radius-card)] p-4">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="font-medium">{c.format_label}</p>
                  <p className="text-xs text-muted">
                    {c.deliverables}
                    {c.terms.length > 0 && ` · ${c.terms.join(", ")}`}
                  </p>
                </div>
                <div className="flex gap-1">
                  <Button size="sm" variant="ghost" onClick={() => edit(c)} aria-label={`Edit your ${c.format_label.toLowerCase()} rate`}>
                    Edit
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => remove.mutate(c.format)} aria-label={`Delete your ${c.format_label.toLowerCase()} rate`}>
                    <Trash2 aria-hidden />
                  </Button>
                </div>
              </div>
              <dl className="mt-3 grid grid-cols-2 gap-3">
                <div>
                  <dt className="text-[11px] font-semibold uppercase tracking-[0.1em] text-muted">Your rate</dt>
                  <dd className="num mt-0.5 font-display text-xl font-semibold">{inr(c.amount)}</dd>
                  <dd className="mt-1">
                    <SourceBadge source="manual" />
                  </dd>
                </div>
                <div>
                  <dt className="text-[11px] font-semibold uppercase tracking-[0.1em] text-muted">Estimated range</dt>
                  {c.estimate_now.range ? (
                    <>
                      <dd className="num mt-0.5 font-display text-xl font-semibold text-fg-2">{inrRange(c.estimate_now.range.low, c.estimate_now.range.high)}</dd>
                      <dd className="mt-1">
                        <SourceBadge source={c.estimate_now.data_source} />
                      </dd>
                    </>
                  ) : (
                    <dd className="mt-1 text-[13px] text-muted">Not enough data to estimate</dd>
                  )}
                </div>
              </dl>
              {c.note && <p className="mt-2 text-xs text-fg-2">{c.note}</p>}
              <p className="mt-2 text-[11px] text-muted">Saved {shortDate(c.saved_at, true)}</p>
            </li>
          ))}
        </ul>
      )}

      <div className="card-surface grid gap-5 rounded-[var(--radius-card)] p-5 lg:grid-cols-[1fr_1.2fr]">
        <form
          aria-label="Price a format"
          className="space-y-3"
          onSubmit={(ev) => {
            ev.preventDefault();
            const n = Number(amount.replace(/[^\d]/g, ""));
            if (!n || n < 100) {
              setAmountErr("Enter your rate in rupees, ₹100 or more.");
              return;
            }
            setAmountErr("");
            save.mutate(n);
          }}
        >
          <p className="flex items-center gap-1.5 text-sm font-medium">
            <Calculator className="size-4 text-accent" aria-hidden /> Price a format
          </p>
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2 sm:col-span-1">
              <Label htmlFor="rc-format">Content format</Label>
              <Select id="rc-format" value={format} onChange={(ev) => setFormat(ev.target.value as Format)}>
                {(rates.data?.formats ?? [{ key: "reel" as Format, label: "Instagram reel" }]).map((f) => (
                  <option key={f.key} value={f.key}>
                    {f.label}
                  </option>
                ))}
              </Select>
            </div>
            <div className="col-span-2 sm:col-span-1">
              <Label htmlFor="rc-count">How many</Label>
              <Select id="rc-count" value={count} onChange={(ev) => setCount(Number(ev.target.value))}>
                {[1, 2, 3, 4, 5].map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="rc-usage">Paid usage rights</Label>
              <Select id="rc-usage" value={usage} onChange={(ev) => setUsage(Number(ev.target.value))}>
                {DAYS.map((d) => (
                  <option key={d} value={d}>
                    {d ? `${d} days` : "None"}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="rc-excl">Exclusivity</Label>
              <Select id="rc-excl" value={excl} onChange={(ev) => setExcl(Number(ev.target.value))}>
                {DAYS.map((d) => (
                  <option key={d} value={d}>
                    {d ? `${d} days` : "None"}
                  </option>
                ))}
              </Select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 border-t border-line pt-3">
            <div>
              <Label htmlFor="rc-amount">Your rate (₹)</Label>
              <Input
                id="rc-amount"
                inputMode="numeric"
                value={amount}
                onChange={(ev) => setAmount(ev.target.value)}
                placeholder={e?.range ? String(Math.round((e.range.low + e.range.high) / 2)) : "5000"}
                aria-invalid={!!amountErr}
                aria-describedby={amountErr ? "rc-amount-err" : undefined}
              />
            </div>
            <div>
              <Label htmlFor="rc-note">Note (optional)</Label>
              <Input id="rc-note" value={note} onChange={(ev) => setNote(ev.target.value)} maxLength={140} placeholder="Includes one revision" />
            </div>
          </div>
          {amountErr && (
            <p id="rc-amount-err" role="alert" className="text-xs text-danger">
              {amountErr}
            </p>
          )}
          <Button type="submit" variant="primary" loading={save.isPending}>
            {!save.isPending && <Save aria-hidden />} Save as your rate
          </Button>
          <FieldHint>Saving a format again replaces its rate.</FieldHint>
        </form>

        <div aria-live="polite" className={cn("transition-opacity", est.isFetching && "opacity-60")}>
          {est.isError && <ErrorState error={est.error} onRetry={() => est.refetch()} />}
          {e && (
            <div className="space-y-4">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-muted">Estimated range · {e.deliverables}</p>
                {e.range ? (
                  <>
                    <p className="num mt-1 font-display text-3xl font-semibold">{inrRange(e.range.low, e.range.high)}</p>
                    <p className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-fg-2">
                      {e.data_label} <SourceBadge source={e.data_source} />
                      {e.confidence && <Badge size="sm" variant="outline">{e.confidence} confidence</Badge>}
                    </p>
                  </>
                ) : (
                  <p className="mt-1 flex items-center gap-1.5 text-sm text-fg-2">
                    <AlertCircle className="size-4 text-warn" aria-hidden /> Not enough data to estimate this yet. You can still save your own rate.
                  </p>
                )}
              </div>
              {e.metrics.length > 0 && (
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.1em] text-muted">Numbers used</p>
                  <ul className="mt-1.5 divide-y divide-line rounded-2xl border border-line">
                    {e.metrics.map((m) => (
                      <li key={m.key} className="px-3 py-2 text-[13px]">
                        <span className="flex flex-wrap items-center gap-2">
                          <span className="flex-1 text-fg-2">{m.label}</span>
                          <span className="num font-medium">{m.value}</span>
                          <SourceBadge source={m.source} />
                        </span>
                        {m.note && <span className="mt-0.5 block text-[11px] text-muted">{m.note}</span>}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {e.missing.length > 0 && (
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.1em] text-muted">Missing, not guessed</p>
                  <ul className="mt-1.5 space-y-1.5">
                    {e.missing.map((m) => (
                      <li key={m.key} className="text-[13px]">
                        <span className="font-medium">{m.label}:</span> <span className="text-fg-2">{m.effect}</span>{" "}
                        <Link to={m.path} className="inline-flex items-center gap-0.5 text-accent hover:underline">
                          {m.fix} <ArrowRight className="size-3" aria-hidden />
                        </Link>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {e.assumptions.length > 0 && (
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.1em] text-muted">Assumptions</p>
                  <ul className="mt-1.5 list-disc space-y-1 pl-5 text-[13px] text-fg-2">
                    {e.assumptions.map((a) => (
                      <li key={a}>{a}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
