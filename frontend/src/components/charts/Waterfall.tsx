import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { FairPrice } from "@/lib/api-types";
import { inr } from "@/lib/format";

type Kind = "base" | "up" | "down" | "total";
interface Row {
  label: string;
  offset: number;
  value: number;
  kind: Kind;
  amount: number;
  running: number;
  reason: string;
  display: string;
}

const COLOR: Record<Kind, string> = {
  base: "var(--chart-base)",
  total: "var(--chart-base)",
  up: "var(--chart-up)",
  down: "var(--chart-down)",
};

const SHORT: Record<string, string> = {
  base: "Reach base",
  engagement: "Engagement",
  fit: "Audience fit",
  consistency: "Consistency",
  safety: "Brand safety",
  trust: "Trust",
  ai: "AI review",
  floor: "Production floor",
  deliverables: "Deliverables",
  terms: "Usage rights",
};

type WaterfallInput = Pick<FairPrice, "steps" | "total" | "base">;

export function toRows(fp: WaterfallInput): Row[] {
  const rows: Row[] = [];
  let running = 0;
  for (const s of fp.steps) {
    if (s.key === "base") {
      running = s.amount;
      rows.push({ label: SHORT.base, offset: 0, value: s.amount, kind: "base", amount: s.amount, running, reason: s.reason, display: inr(s.amount) });
      continue;
    }
    if (Math.abs(s.amount) < 1) continue;
    const before = running;
    running += s.amount;
    const up = s.amount >= 0;
    rows.push({
      label: SHORT[s.key] ?? s.label,
      offset: up ? before : running,
      value: Math.abs(s.amount),
      kind: up ? "up" : "down",
      amount: s.amount,
      running,
      reason: s.reason,
      display: `${up ? "+" : "−"}${inr(Math.abs(s.amount))}`,
    });
  }
  rows.push({ label: "Fair price", offset: 0, value: fp.total, kind: "total", amount: fp.total, running: fp.total, reason: "Sum of the steps above.", display: inr(fp.total) });
  return rows;
}

function TipContent({ active, payload }: { active?: boolean; payload?: { payload: Row }[] }) {
  if (!active || !payload?.length) return null;
  const r = payload[payload.length - 1].payload;
  return (
    <div className="max-w-64 rounded-xl border border-line-strong bg-[var(--surface-solid)] px-3 py-2 text-xs shadow-lg">
      <p className="font-semibold text-fg">{r.label}</p>
      <p className="num mt-0.5 text-fg-2">
        {r.kind === "base" || r.kind === "total" ? r.display : `${r.display} → ${inr(r.running)}`}
      </p>
      <p className="mt-1 leading-relaxed text-muted">{r.reason}</p>
    </div>
  );
}

export function Waterfall({ fp, height }: { fp: WaterfallInput; height?: number }) {
  const rows = toRows(fp);
  const max = Math.max(...rows.map((r) => r.offset + r.value));
  const h = height ?? rows.length * 38 + 24;
  return (
    <div
      role="img"
      aria-label={`Price breakdown: reach base ${inr(fp.base)}, adjustments, fair price ${inr(fp.total)}. Full steps are listed below the chart.`}
      className="w-full"
    >
      <ResponsiveContainer width="100%" height={h}>
        <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 64, bottom: 4, left: 4 }} barCategoryGap={10}>
          <XAxis type="number" hide domain={[0, Math.ceil(max * 1.04)]} />
          <YAxis
            type="category"
            dataKey="label"
            width={112}
            tickLine={false}
            axisLine={false}
            tick={{ fill: "var(--muted)", fontSize: 12 }}
          />
          <Tooltip cursor={{ fill: "var(--surface-2)" }} content={<TipContent />} isAnimationActive={false} />
          <Bar dataKey="offset" stackId="w" fill="transparent" isAnimationActive={false} />
          <Bar dataKey="value" stackId="w" radius={4} maxBarSize={22} isAnimationActive={false}>
            {rows.map((r) => (
              <Cell key={r.label} fill={COLOR[r.kind]} />
            ))}
            <LabelList
              dataKey="display"
              position="right"
              offset={8}
              style={{ fill: "var(--fg-2)", fontSize: 12, fontVariantNumeric: "tabular-nums", fontWeight: 600 }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted" aria-hidden>
        <Key color={COLOR.base} label="Base and fair price" />
        <Key color={COLOR.up} label="+ Raises price" />
        <Key color={COLOR.down} label="− Lowers price" />
      </div>
    </div>
  );
}

function Key({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="size-2.5 rounded-[3px]" style={{ background: color }} />
      {label}
    </span>
  );
}
