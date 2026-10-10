import { useMutation, useQuery } from "@tanstack/react-query";
import { CalendarCheck, Lock, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ErrorState } from "@/components/shared/Bits";
import { KitCard } from "@/components/shared/KitCard";
import { Wordmark } from "@/components/shared/Wordmark";
import { Button } from "@/components/ui/button";
import { Input, Label, Segmented, Skeleton, Textarea } from "@/components/ui/form";
import { Dialog, DialogContent } from "@/components/ui/overlays";
import { api, post } from "@/lib/api";
import { inr } from "@/lib/format";
import type { Kit } from "@/lib/kit-types";
import { useTheme } from "@/lib/theme";
import NotFound from "./NotFound";

export default function LinkInBio() {
  useTheme("creator");
  const { handle = "" } = useParams();
  const [open, setOpen] = useState(false);
  const q = useQuery({ queryKey: ["public", handle], queryFn: () => api<Kit>(`/public/${handle}`), retry: false });
  if (q.isError && (q.error as { status?: number }).status === 404) return <NotFound />;

  return (
    <div className="theme-creator grain relative min-h-dvh">
      <div className="aurora" aria-hidden>
        <span />
      </div>
      <div className="relative z-10 mx-auto max-w-2xl px-4 py-6 sm:py-10">
        <main id="main">
          {q.isError && <ErrorState error={q.error} onRetry={() => q.refetch()} />}
          {!q.data && !q.isError && <Skeleton className="h-[640px] rounded-[28px]" />}
          {q.data && (
            <KitCard
              kit={q.data}
              headingLevel={1}
              footer={
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p className="flex items-center gap-1.5 text-xs text-muted">
                    <ShieldCheck className="size-4 text-success" aria-hidden /> Payment held in escrow until the post is verified.
                  </p>
                  <Button variant="primary" size="lg" onClick={() => setOpen(true)}>
                    <CalendarCheck aria-hidden /> Book {q.data.name.split(" ")[0]}
                  </Button>
                </div>
              }
            />
          )}
        </main>
        <footer className="mt-8 flex items-center justify-center gap-2 text-xs text-muted">
          <Link to="/" aria-label="JodiDar AI home" className="rounded-lg">
            <Wordmark />
          </Link>
          <span>· Fair prices, escrow, UPI payouts</span>
        </footer>
      </div>
      {q.data && <BookDialog kit={q.data} open={open} onOpenChange={setOpen} />}
    </div>
  );
}

function BookDialog({ kit, open, onOpenChange }: { kit: Kit; open: boolean; onOpenChange: (v: boolean) => void }) {
  const [brand, setBrand] = useState("");
  const [email, setEmail] = useState("");
  const [budget, setBudget] = useState(kit.from_rate != null ? String(kit.from_rate) : "");
  const [deliverable, setDeliverable] = useState<"reel" | "reel_stories" | "bundle">("reel");
  const [message, setMessage] = useState("");
  const [budgetErr, setBudgetErr] = useState("");
  const book = useMutation({
    mutationFn: () => post<{ message: string; track: string }>(`/public/${kit.handle}/book`, { brand_name: brand, email, budget: Number(budget.replace(/[^\d]/g, "")), deliverable, message: message || null }),
  });
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent sheet title={`Book ${kit.name}`} description="Your request goes to their JodiDar deal inbox.">
        {book.isSuccess ? (
          <div className="text-center">
            <p className="font-display text-lg font-semibold">Request sent</p>
            <p className="mt-1 text-sm text-fg-2">{book.data.message}</p>
            <div className="mt-5 flex flex-wrap justify-center gap-2">
              {/* A full page load, so the console opens as the guest brand (?as= is read on load). */}
              <Button asChild variant="primary">
                <a href={book.data.track}>Follow this booking</a>
              </Button>
              <Button variant="outline" onClick={() => onOpenChange(false)}>
                Done
              </Button>
            </div>
          </div>
        ) : (
          <form
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              if (Number(budget.replace(/[^\d]/g, "")) < 500) {
                setBudgetErr("Enter a budget of at least ₹500.");
                return;
              }
              setBudgetErr("");
              book.mutate();
            }}
          >
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <Label htmlFor="bk-brand">Brand</Label>
                <Input id="bk-brand" value={brand} onChange={(e) => setBrand(e.target.value)} required minLength={2} autoComplete="organization" />
              </div>
              <div>
                <Label htmlFor="bk-email">Work email</Label>
                <Input id="bk-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
                <p className="mt-1 text-xs text-muted">Demo: this email isn't stored or sent anywhere.</p>
              </div>
            </div>
            <div>
              <p className="mb-1.5 text-[13px] font-medium text-fg-2">What you need</p>
              <Segmented
                label="Deliverable"
                value={deliverable}
                onChange={setDeliverable}
                options={[
                  { value: "reel", label: "1 reel" },
                  { value: "reel_stories", label: "Reel + 2 stories" },
                  { value: "bundle", label: "2 reels" },
                ]}
              />
            </div>
            <div>
              <Label htmlFor="bk-budget">Budget (₹)</Label>
              <Input id="bk-budget" inputMode="numeric" required placeholder="e.g. 10,000" value={budget} onChange={(e) => setBudget(e.target.value)} />
              {budgetErr && (
                <p role="alert" className="mt-1 text-xs text-danger">
                  {budgetErr}
                </p>
              )}
              {kit.from_rate != null && <p className="mt-1 text-xs text-muted">Rates start at {inr(kit.from_rate)} for one reel.</p>}
            </div>
            <div>
              <Label htmlFor="bk-msg">Brief (optional)</Label>
              <Textarea id="bk-msg" value={message} onChange={(e) => setMessage(e.target.value)} className="min-h-20" />
            </div>
            {book.isError && (
              <p role="alert" className="text-sm text-danger">
                {(book.error as Error).message}
              </p>
            )}
            <Button type="submit" variant="primary" size="lg" className="w-full" loading={book.isPending}>
              <Lock aria-hidden /> Send booking request
            </Button>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
