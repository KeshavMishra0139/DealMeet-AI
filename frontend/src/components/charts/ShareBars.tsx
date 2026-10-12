import { Bar, BarChart, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export interface ShareRow {
  label: string;
  /** 0..1 */
  share: number;
}

const pct = (v: number) => `${Math.round(v * 100)}%`;

function TipContent({ active, payload }: { active?: boolean; payload?: { payload: ShareRow }[] }) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  return (
    <div className="rounded-xl border border-line-strong bg-[var(--surface-solid)] px-3 py-2 text-xs shadow-lg">
      <p className="font-semibold text-fg">{r.label}</p>
      <p className="num mt-0.5 text-fg-2">{pct(r.share)} of the audience</p>
    </div>
  );
}

/**
 * One series of shares (an audience by age or by city) as horizontal bars, one hue,
 * values at the bar tips, a hover tooltip, and the same numbers in a table for
 * screen readers.
 */
export function ShareBars({ rows, caption }: { rows: ShareRow[]; caption: string }) {
  const h = rows.length * 30 + 8;
  return (
    <figure className="w-full">
      <div aria-hidden>
        <ResponsiveContainer width="100%" height={h}>
          <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 44, bottom: 4, left: 4 }} barCategoryGap={8}>
            <XAxis type="number" hide domain={[0, Math.max(...rows.map((r) => r.share), 0.01)]} />
            <YAxis type="category" dataKey="label" width={88} tickLine={false} axisLine={false} tick={{ fill: "var(--muted)", fontSize: 12 }} />
            <Tooltip cursor={{ fill: "var(--surface-2)" }} content={<TipContent />} isAnimationActive={false} />
            <Bar dataKey="share" fill="var(--chart-base)" radius={[0, 4, 4, 0]} maxBarSize={18} isAnimationActive={false}>
              <LabelList
                dataKey="share"
                position="right"
                offset={8}
                formatter={(v: unknown) => pct(Number(v))}
                style={{ fill: "var(--fg-2)", fontSize: 12, fontVariantNumeric: "tabular-nums", fontWeight: 600 }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <table className="sr-only">
        <caption>{caption}</caption>
        <tbody>
          {rows.map((r) => (
            <tr key={r.label}>
              <th scope="row">{r.label}</th>
              <td>{pct(r.share)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <figcaption className="sr-only">{caption}</figcaption>
    </figure>
  );
}
