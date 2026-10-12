import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Clock, Send, ShieldCheck, Wand2, X } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/form";
import { Dialog, DialogContent } from "@/components/ui/overlays";
import { api, post } from "@/lib/api";
import { cn } from "@/lib/utils";

type Role = "creator" | "brand";

interface Outcome {
  tool: string | null;
  mode?: "read" | "draft" | "confirm" | "confirmed";
  result?: Record<string, unknown>;
  proposal?: { id: string; summary: string; expires_in_s: number };
  reply?: string;
  chosen_by?: "ai" | "rules";
}

const SUGGESTIONS: Record<Role, string[]> = {
  creator: ["Explain my fair rate", "Are my views growing?", "Make me a growth plan", "Draft a pitch to Thalam Foods", "Save my media kit as a new version"],
  brand: ["Draft a new campaign brief: Festive launch", "Publish my draft campaign", "Pause the winter hoodie drop", "Status of the winter hoodie drop", "Send my draft offer"],
};

const TOOL_LABEL: Record<string, string> = {
  explain_metric: "Explained a number",
  explain_price: "Explained your price",
  growth_plan: "Made a growth plan",
  create_kit_version: "Saved a media kit version",
  draft_pitch: "Drafted a pitch (not sent)",
  send_pitch: "Pitch sent",
  campaign_status: "Campaign status",
  draft_campaign_brief: "Drafted a campaign (hidden from creators)",
  draft_offer: "Drafted an offer (not sent)",
  send_offer: "Offer sent",
  publish_campaign: "Campaign published",
  pause_campaign: "Campaign paused",
};

/** Ask the assistant to do something. It reads and drafts on its own; anything that
 * sends, publishes or touches money waits for your Confirm, for up to 10 minutes. */
export function ActionAssistant({ role, className, compact = false }: { role: Role; className?: string; compact?: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button variant={compact ? "ghost" : "outline"} size={compact ? "icon-sm" : "sm"} className={className} onClick={() => setOpen(true)} aria-label="Assistant: do something for me">
        <Wand2 aria-hidden /> {!compact && "Assistant"}
      </Button>
      {open && <AssistantDialog role={role} onClose={() => setOpen(false)} />}
    </>
  );
}

function AssistantDialog({ role, onClose }: { role: Role; onClose: () => void }) {
  const qc = useQueryClient();
  const [msg, setMsg] = useState("");
  const [out, setOut] = useState<Outcome | null>(null);
  const pending = useQuery({ queryKey: ["proposals", role], queryFn: () => api<{ items: { id: string; tool: string; summary: string; expires_in_s: number }[] }>("/assistant/proposals") });
  const ask = useMutation({
    mutationFn: (message: string) => post<Outcome>("/assistant/act", { message }),
    onSuccess: (o) => {
      setOut(o);
      void qc.invalidateQueries({ queryKey: ["proposals", role] });
      if (o.mode === "draft") void qc.invalidateQueries();
    },
    onError: (e) => setOut({ tool: null, reply: (e as Error).message }),
  });
  const run = (m: string) => {
    if (m.trim().length < 2) return;
    setMsg(m);
    ask.mutate(m.trim());
  };
  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent sheet title="Assistant" description="It reads and drafts for you. Anything that sends, publishes or touches money waits for your Confirm.">
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            run(msg);
          }}
        >
          <Input value={msg} onChange={(e) => setMsg(e.target.value)} placeholder={role === "brand" ? "Publish my draft campaign" : "Draft a pitch to Thalam Foods"} aria-label="What should the assistant do?" maxLength={300} />
          <Button type="submit" variant="primary" loading={ask.isPending} aria-label="Ask the assistant">
            {!ask.isPending && <Send aria-hidden />}
          </Button>
        </form>
        <div className="mt-3 flex flex-wrap gap-1.5">
          {SUGGESTIONS[role].map((s) => (
            <button key={s} type="button" onClick={() => run(s)} className="rounded-full border border-line bg-surface px-3 py-1 text-xs text-fg-2 hover:border-accent/60 hover:text-fg">
              {s}
            </button>
          ))}
        </div>

        {out && (
          <div className="mt-5" aria-live="polite">
            {out.tool === null && <p className="text-sm text-fg-2">{out.reply}</p>}
            {out.proposal && <ProposalCard p={out.proposal} role={role} onDone={(o) => setOut(o)} />}
            {out.result && <ResultCard tool={out.tool ?? ""} result={out.result} confirmed={out.mode === "confirmed"} />}
            {out.chosen_by && <p className="mt-2 text-[11px] text-muted">Tool chosen by {out.chosen_by === "ai" ? "AI" : "simple rules"}; arguments checked before anything ran.</p>}
          </div>
        )}

        {pending.data && pending.data.items.filter((p) => p.id !== out?.proposal?.id).length > 0 && (
          <div className="mt-5 border-t border-line pt-4">
            <p className="text-xs font-semibold uppercase tracking-[0.1em] text-muted">Waiting for your confirmation</p>
            <div className="mt-2 space-y-2">
              {pending.data.items
                .filter((p) => p.id !== out?.proposal?.id)
                .map((p) => (
                  <ProposalCard key={p.id} p={p} role={role} onDone={(o) => setOut(o)} />
                ))}
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function ProposalCard({ p, role, onDone }: { p: { id: string; summary: string; expires_in_s: number }; role: Role; onDone: (o: Outcome) => void }) {
  const qc = useQueryClient();
  const [left, setLeft] = useState(p.expires_in_s);
  useEffect(() => {
    const t = setInterval(() => setLeft((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(t);
  }, []);
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["proposals", role] });
    void qc.invalidateQueries();
  };
  const confirm = useMutation({
    mutationFn: () => post<Outcome>(`/assistant/proposals/${p.id}/confirm`),
    onSuccess: (o) => {
      refresh();
      onDone(o);
      toast.success(TOOL_LABEL[o.tool ?? ""] ?? "Done");
    },
    onError: (e) => toast.error((e as Error).message),
  });
  const cancel = useMutation({
    mutationFn: () => post(`/assistant/proposals/${p.id}/cancel`),
    onSuccess: () => (refresh(), onDone({ tool: null, reply: "Cancelled. Nothing happened." })),
  });
  const expired = left <= 0;
  return (
    <div className={cn("rounded-2xl border border-accent/40 bg-accent-soft p-4", expired && "opacity-60")}>
      <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.1em] text-accent">
        <ShieldCheck className="size-4" aria-hidden /> Needs your confirmation
      </p>
      <p className="mt-1.5 text-sm font-medium">{p.summary}</p>
      <p className="mt-1 flex items-center gap-1 text-xs text-fg-2">
        <Clock className="size-3.5" aria-hidden /> {expired ? "Expired. Ask again to make a new one." : `Expires in ${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}. Runs once.`}
      </p>
      <div className="mt-3 flex gap-2">
        <Button size="sm" variant="primary" disabled={expired} loading={confirm.isPending} onClick={() => confirm.mutate()}>
          <CheckCircle2 aria-hidden /> Confirm
        </Button>
        <Button size="sm" variant="ghost" disabled={expired} loading={cancel.isPending} onClick={() => cancel.mutate()}>
          <X aria-hidden /> Cancel
        </Button>
      </div>
    </div>
  );
}

function ResultCard({ tool, result, confirmed }: { tool: string; result: Record<string, unknown>; confirmed: boolean }) {
  const answer = typeof result.answer === "string" ? result.answer : null;
  const label = typeof result.label === "string" ? result.label : null;
  const status = typeof result.status === "string" ? result.status : null;
  const missing = Array.isArray(result.missing) ? (result.missing as { message: string }[]) : [];
  return (
    <div className="rounded-2xl border border-line bg-surface-2 p-4 text-sm">
      <p className="flex flex-wrap items-center gap-2 font-medium">
        {TOOL_LABEL[tool] ?? tool} {confirmed && <Badge size="sm" variant="success">Confirmed</Badge>}
      </p>
      {answer && <p className="mt-1.5 leading-relaxed text-fg-2">{answer}</p>}
      {label && (
        <p className="num mt-1.5 font-display text-xl font-semibold">
          {label} <span className="text-xs font-normal text-muted">{String(result.data_label ?? "")} · an estimate</span>
        </p>
      )}
      {status && !answer && <p className="mt-1 text-fg-2">Status: {status}</p>}
      {typeof result.title === "string" && <p className="mt-1 text-fg-2">{result.title}</p>}
      {typeof result.subject === "string" && <p className="mt-1 text-fg-2">“{result.subject}”</p>}
      {typeof result.total === "number" && Array.isArray(result.goals) && <p className="mt-1 text-fg-2">{result.total} goals, each with a target and a deadline. See them on Home.</p>}
      {missing.length > 0 && (
        <ul className="mt-1 list-disc pl-5 text-xs text-fg-2">
          {missing.map((m) => (
            <li key={m.message}>{m.message}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
