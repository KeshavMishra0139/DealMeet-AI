import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { HelpCircle, ListChecks, MessageCircleQuestion, Send } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { SourceBadge } from "@/components/shared/SourceBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/form";
import { Dialog, DialogContent } from "@/components/ui/overlays";
import { useI18n } from "@/i18n";
import { api, post } from "@/lib/api";
import { useCreatorId } from "@/lib/session";
import { cn } from "@/lib/utils";

interface Answer {
  question: string;
  answer: string;
  uncertain: string;
  next_steps: string[];
  used: { key: string; label: string; value: string; source: string }[];
  trend_known: boolean;
  written_by: "ai" | "template";
  cached: boolean;
}

/** "Ask" about your own numbers. Answers come only from your data and list what they used. */
export function AskButton({ compact = false, className }: { compact?: boolean; className?: string }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button variant={compact ? "ghost" : "outline"} size={compact ? "sm" : "md"} className={className} onClick={() => setOpen(true)} aria-label="Ask about your numbers">
        <MessageCircleQuestion aria-hidden /> Ask
      </Button>
      {open && <AskDialog onClose={() => setOpen(false)} />}
    </>
  );
}

function AskDialog({ onClose }: { onClose: () => void }) {
  const { lang } = useI18n();
  const id = useCreatorId();
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const sugg = useQuery({ queryKey: ["ask-suggestions"], queryFn: () => api<{ questions: string[] }>("/assistant/suggestions"), staleTime: Infinity });
  const ask = useMutation({ mutationFn: (question: string) => post<Answer>("/assistant/ask", { question, lang }) });
  const plan = useMutation({
    mutationFn: () => post<{ total: number }>("/assistant/plan"),
    onSuccess: (p) => {
      void qc.invalidateQueries({ queryKey: ["goals", id] });
      toast.success(`Plan saved: ${p.total} goals`, { description: "Each has a target and a deadline. Track them on Home." });
    },
    onError: (e) => toast.error((e as Error).message),
  });
  const a = ask.data;
  const run = (question: string) => {
    if (question.trim().length < 2) return;
    setQ(question);
    ask.mutate(question.trim());
  };

  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent sheet title="Ask about your numbers" description="Answers use only your own data, and list every number they used.">
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            run(q);
          }}
        >
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Are my views growing?" aria-label="Your question" maxLength={300} />
          <Button type="submit" variant="primary" loading={ask.isPending} aria-label="Ask">
            {!ask.isPending && <Send aria-hidden />}
          </Button>
        </form>
        <div className="mt-3 flex flex-wrap gap-1.5">
          {sugg.data?.questions.map((s) => (
            <button key={s} type="button" onClick={() => run(s)} className="rounded-full border border-line bg-surface px-3 py-1 text-xs text-fg-2 hover:border-accent/60 hover:text-fg">
              {s}
            </button>
          ))}
        </div>

        {ask.isError && (
          <p role="alert" className="mt-4 text-sm text-danger">
            {(ask.error as Error).message}
          </p>
        )}

        {a && (
          <div className="mt-5 space-y-4" aria-live="polite">
            <p className="text-[15px] leading-relaxed">{a.answer}</p>
            <div className="flex gap-2 rounded-2xl bg-surface-2 p-3 text-[13px] text-fg-2">
              <HelpCircle className="mt-0.5 size-4 shrink-0 text-muted" aria-hidden />
              <span>
                <span className="font-medium text-fg">What's uncertain: </span>
                {a.uncertain}
              </span>
            </div>
            {a.next_steps.length > 0 && (
              <ul className="list-disc space-y-1 pl-5 text-[13px] text-fg-2">
                {a.next_steps.map((s) => (
                  <li key={s}>{s}</li>
                ))}
              </ul>
            )}
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.1em] text-muted">Numbers used</p>
              <ul className="mt-2 divide-y divide-line rounded-2xl border border-line">
                {a.used.map((f) => (
                  <li key={f.key} className="flex flex-wrap items-center gap-2 px-3 py-2 text-[13px]">
                    <span className="flex-1 text-fg-2">{f.label}</span>
                    <span className="num font-medium">{f.value}</span>
                    <SourceBadge source={f.source} />
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-[11px] text-muted">
                {a.written_by === "ai" ? "Worded by AI from these numbers only, checked for promises." : "Worded from a template using these numbers."} Estimates, not promises.
              </p>
            </div>
          </div>
        )}

        <div className={cn("mt-5 flex flex-wrap items-center gap-2 border-t border-line pt-4")}>
          <Button variant="outline" loading={plan.isPending} onClick={() => plan.mutate()}>
            {!plan.isPending && <ListChecks aria-hidden />} Make me a plan
          </Button>
          <Link to="/creator" onClick={onClose} className="text-xs text-muted hover:text-fg">
            Goals show on Home
          </Link>
        </div>
      </DialogContent>
    </Dialog>
  );
}
