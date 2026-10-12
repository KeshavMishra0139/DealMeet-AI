import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, CircleDashed, Clock } from "lucide-react";
import { Progress } from "@/components/ui/form";
import { api } from "@/lib/api";
import { inr, shortDate } from "@/lib/format";

interface Goal {
  move_id: string;
  title: string;
  metric: string;
  unit: "rupees" | "count";
  target: number;
  current: number;
  deadline: string;
  done: boolean;
  late: boolean;
  tracked: boolean;
}

interface GoalPlan {
  goals: Goal[];
  done: number;
  total: number;
  data_changes: { at: string; reason: string; changes: string[] }[];
  note: string;
}

/** Goals from "Make me a plan": a metric, a target and a deadline for each move, with progress from your data. */
export function Goals({ creatorId }: { creatorId: string }) {
  const q = useQuery({ queryKey: ["goals", creatorId], queryFn: () => api<{ plan: GoalPlan | null }>(`/creators/${creatorId}/goals`) });
  const p = q.data?.plan;
  if (!p) return null;
  const fmt = (g: Goal, v: number) => (g.unit === "rupees" ? inr(v) : String(v));
  const latest = p.data_changes[p.data_changes.length - 1];
  return (
    <section aria-labelledby="goals" className="card-surface mt-6 rounded-[var(--radius-card)] p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="goals" className="font-display text-lg font-semibold">
          Your goals
        </h2>
        <p className="text-xs text-muted">
          {p.done} of {p.total} done
        </p>
      </div>
      <ul className="mt-3 space-y-3">
        {p.goals.map((g) => (
          <li key={g.move_id} className="text-[13px]">
            <div className="flex items-start gap-2">
              {g.done ? <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-success" aria-hidden /> : <CircleDashed className="mt-0.5 size-4 shrink-0 text-muted" aria-hidden />}
              <div className="min-w-0 flex-1">
                <p className="font-medium">{g.title}</p>
                <p className="text-xs text-muted">
                  {g.metric}: {fmt(g, g.current)} of {fmt(g, g.target)} · by {shortDate(g.deadline)}
                  {g.late && (
                    <span className="ml-1 inline-flex items-center gap-1 text-warn">
                      <Clock className="size-3" aria-hidden /> past the deadline
                    </span>
                  )}
                  {!g.tracked && " · tick the move when it's done"}
                </p>
                <Progress value={Math.min(100, (g.current / Math.max(1, g.target)) * 100)} className="mt-1.5 h-1.5" label={`${g.metric} progress`} tone={g.done ? "success" : "signature"} />
              </div>
            </div>
          </li>
        ))}
      </ul>
      {latest && (
        <div className="mt-4 rounded-2xl bg-surface-2 p-3 text-[13px] text-fg-2">
          <p className="font-medium text-fg">
            Updated {shortDate(latest.at)}: {latest.reason.toLowerCase()}
          </p>
          <ul className="mt-1 space-y-0.5">
            {latest.changes.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </div>
      )}
      <p className="mt-3 text-[11px] text-muted">{p.note}</p>
    </section>
  );
}
