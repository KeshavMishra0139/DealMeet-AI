import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { ArrowRight, Check, IndianRupee, RotateCcw, Sparkles, TrendingUp } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { RangeValue } from "@/components/shared/Estimate";
import { EstimateNote, WhyPopover } from "@/components/shared/Why";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/form";
import { Dialog, DialogContent } from "@/components/ui/overlays";
import { useI18n, useTr } from "@/i18n";
import { post } from "@/lib/api";
import type { Move, Plan } from "@/lib/api-types";
import { cn } from "@/lib/utils";

const CATEGORY = {
  money: { label: "cat.money", icon: IndianRupee },
  growth: { label: "cat.growth", icon: TrendingUp },
  opportunity: { label: "cat.opportunity", icon: Sparkles },
} as const;

const RESULTS = [
  { value: "worked", label: "move.worked" },
  { value: "partly", label: "move.partly" },
  { value: "no", label: "move.no" },
] as const;

export function MoveCard({ move, creatorId, index }: { move: Move; creatorId: string; index: number }) {
  const { t, pick } = useI18n();
  const tr = useTr();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const title = pick(move.title, move.hi?.title);
  const [result, setResult] = useState<(typeof RESULTS)[number]["value"]>("worked");
  const [amount, setAmount] = useState("");
  const [celebrate, setCelebrate] = useState(false);
  const cat = CATEGORY[move.category];
  const done = move.status === "done";
  const asksAmount = move.category === "money" && /rate|bundle/i.test(move.kind);

  const mutate = useMutation({
    mutationFn: (body: object) => post<Plan>(`/creators/${creatorId}/moves/${move.id}`, body),
    onSuccess: async (_, body) => {
      if ((body as { action: string }).action === "done") {
        setCelebrate(true);
        setTimeout(() => setCelebrate(false), 1400);
      }
      await qc.invalidateQueries({ queryKey: ["home", creatorId] });
    },
  });

  return (
    <motion.article
      aria-labelledby={`${move.id}-title`}
      whileHover={done ? undefined : { y: -4 }}
      transition={{ type: "spring", stiffness: 320, damping: 26 }}
      className={cn(
        "card-surface relative flex h-full flex-col overflow-hidden rounded-[26px] p-5 sm:p-6",
        done && "border-success/30",
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="inline-flex items-center gap-2 text-xs font-medium text-muted">
          <span className="num grid size-6 place-items-center rounded-full bg-accent-soft text-[12px] text-accent">{index + 1}</span>
          <cat.icon className="size-3.5" aria-hidden />
          {t(cat.label)}
        </span>
        <span className="flex items-center gap-1.5">
          {move.carried_over && <Badge size="sm">{t("move.carried")}</Badge>}
          <Badge size="sm" variant="outline" title={t(`effort.${move.effort}`)}>
            {t("common.effort")} {move.effort}
          </Badge>
        </span>
      </div>

      <h3 id={`${move.id}-title`} className="mt-4 font-display text-[21px] font-semibold leading-[1.2] tracking-tight sm:text-[22px]">
        {title}
      </h3>
      <p className="mt-2 text-[15px] leading-relaxed text-fg-2">{pick(move.reason, move.hi?.reason)}</p>

      <div className="mt-auto pt-5">
        <div className="rounded-2xl border border-line bg-surface p-3.5">
          <p className="text-xs font-medium text-muted">{t("common.impact")}</p>
          <RangeValue estimate={move.impact} className="mt-1 block" />
          <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1">
            <EstimateNote estimate={move.impact} />
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          {done ? (
            <>
              <span className="inline-flex h-10 items-center gap-2 rounded-xl bg-success-soft px-3.5 text-sm font-medium text-success">
                <Check className="size-4" aria-hidden />
                {t("home.done")}
                {move.outcome?.result && ` · ${t(RESULTS.find((r) => r.value === move.outcome?.result)!.label)}`}
              </span>
              <Button
                variant="ghost"
                size="icon"
                aria-label={t("move.undo", { title })}
                onClick={() => mutate.mutate({ action: "reopen" })}
              >
                <RotateCcw />
              </Button>
            </>
          ) : (
            <Button variant="primary" onClick={() => setOpen(true)}>
              <Check aria-hidden /> {t("home.markDone")}
            </Button>
          )}
          <Button asChild variant="ghost" size="md" className="px-3">
            <Link to={move.cta.to}>
              {tr(move.cta.label)} <ArrowRight aria-hidden />
            </Link>
          </Button>
          <WhyPopover why={move.why} subject={title} label={t("common.why")} className="ml-auto" />
        </div>
      </div>

      <Celebration show={celebrate} />

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent sheet title={t("home.logOutcome")} description={title}>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              mutate.mutate(
                { action: "done", result, amount: amount ? Number(amount.replace(/[^\d]/g, "")) : null },
                { onSuccess: () => setOpen(false) },
              );
            }}
          >
            <fieldset>
              <legend className="mb-2 text-sm text-fg-2">{t("move.shapes")}</legend>
              <div role="radiogroup" aria-label={t("move.outcome")} className="grid grid-cols-3 gap-2">
                {RESULTS.map((r) => (
                  <button
                    type="button"
                    key={r.value}
                    role="radio"
                    aria-checked={result === r.value}
                    onClick={() => setResult(r.value)}
                    className={cn(
                      "min-h-12 rounded-xl border px-2 text-sm font-medium transition-colors",
                      result === r.value ? "border-transparent bg-accent text-accent-fg" : "border-line-strong bg-surface-2 text-fg-2 hover:text-fg",
                    )}
                  >
                    {t(r.label)}
                  </button>
                ))}
              </div>
            </fieldset>
            {asksAmount && result !== "no" && (
              <div className="mt-4">
                <Label htmlFor={`${move.id}-amount`}>{t("move.rateAgreed")}</Label>
                <Input
                  id={`${move.id}-amount`}
                  inputMode="numeric"
                  placeholder="17000"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                />
              </div>
            )}
            {mutate.isError && (
              <p role="alert" className="mt-3 text-sm text-danger">
                {(mutate.error as Error).message}
              </p>
            )}
            <Button type="submit" variant="primary" size="lg" className="mt-5 w-full" loading={mutate.isPending}>
              {t("move.save")}
            </Button>
          </form>
        </DialogContent>
      </Dialog>
    </motion.article>
  );
}

/** A small burst of signature-gradient dots. Skipped when motion is reduced. */
function Celebration({ show }: { show: boolean }) {
  const reduce = useReducedMotion();
  const { t } = useI18n();
  const dots = Array.from({ length: 14 }, (_, i) => i);
  const colors = ["#A78BFA", "#F472B6", "#FB923C"];
  return (
    <AnimatePresence>
      {show && !reduce && (
        <div aria-hidden className="pointer-events-none absolute bottom-16 left-16">
          {dots.map((i) => {
            const angle = (i / dots.length) * Math.PI * 2;
            const dist = 60 + (i % 3) * 22;
            return (
              <motion.span
                key={i}
                className="absolute size-2 rounded-full"
                style={{ background: colors[i % 3] }}
                initial={{ x: 0, y: 0, opacity: 1, scale: 1 }}
                animate={{ x: Math.cos(angle) * dist, y: Math.sin(angle) * dist, opacity: 0, scale: 0.4 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
              />
            );
          })}
        </div>
      )}
      {show && (
        <motion.p
          role="status"
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }}
          className="absolute right-5 top-5 rounded-full bg-success-soft px-3 py-1 text-xs font-semibold text-success"
        >
          {t("move.logged")}
        </motion.p>
      )}
    </AnimatePresence>
  );
}

