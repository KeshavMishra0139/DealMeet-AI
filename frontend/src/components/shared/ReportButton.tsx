import { useMutation } from "@tanstack/react-query";
import { Flag } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { FieldHint, Label, Select, Textarea } from "@/components/ui/form";
import { Dialog, DialogContent } from "@/components/ui/overlays";
import { api, ApiError } from "@/lib/api";
import { hasDemoSession, type Role } from "@/lib/session";

export type ReportTarget = "campaign" | "profile" | "pitch" | "deal";

const REASONS: { value: string; label: string }[] = [
  { value: "scam_or_fraud", label: "Scam or fraud" },
  { value: "fake_numbers", label: "Fake or inflated numbers" },
  { value: "spam", label: "Spam" },
  { value: "harassment", label: "Harassment" },
  { value: "impersonation", label: "Pretending to be someone else" },
  { value: "inappropriate", label: "Inappropriate content" },
  { value: "other", label: "Something else" },
];

const NOUN: Record<ReportTarget, string> = { campaign: "campaign", profile: "profile", pitch: "pitch", deal: "deal" };

/** The side whose demo session should send a report from a public page; null sends only the cookie. */
function publicRole(): Role | null {
  return hasDemoSession("brand") ? "brand" : hasDemoSession("creator") ? "creator" : null;
}

/** Report something to the admins. Signed-in users only, a few a day; the server checks
 * that you can see it (and, for a deal, that you're one of its two sides). */
export function ReportButton({ type, id, role, label, className }: { type: ReportTarget; id: string; role?: Role | null; label?: string; className?: string }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [details, setDetails] = useState("");
  const [needsSignIn, setNeedsSignIn] = useState(false);
  const send = useMutation({
    mutationFn: () =>
      api<{ id: string; duplicate: boolean }>("/reports", {
        method: "POST",
        json: { target_type: type, target_id: id, reason, details: details.trim() || null },
        role: role === undefined ? publicRole() : role,
      }),
    onSuccess: (r) => {
      setOpen(false);
      toast.success(r.duplicate ? "You already reported this" : "Report sent", { description: "An admin reviews it. We don't tell them who reported." });
    },
    onError: (e) => {
      if (e instanceof ApiError && e.status === 401) setNeedsSignIn(true);
      else toast.error((e as Error).message);
    },
  });
  return (
    <>
      <Button size="sm" variant="ghost" className={className} onClick={() => setOpen(true)}>
        <Flag aria-hidden /> {label ?? `Report this ${NOUN[type]}`}
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent title={`Report this ${NOUN[type]}`} description="Admins review every report. You can send 5 a day.">
          {needsSignIn ? (
            <div className="space-y-3">
              <p className="text-sm text-fg-2">Sign in to report. Reports come from accounts so admins can follow up and stop misuse.</p>
              <Button asChild variant="primary">
                <Link to={`/login?next=${encodeURIComponent(window.location.pathname)}`}>Sign in</Link>
              </Button>
            </div>
          ) : (
            <form
              className="space-y-3"
              onSubmit={(e) => {
                e.preventDefault();
                send.mutate();
              }}
            >
              <div>
                <Label htmlFor={`rep-reason-${id}`}>What's wrong</Label>
                <Select id={`rep-reason-${id}`} value={reason} onChange={(e) => setReason(e.target.value)} required>
                  <option value="">Choose one</option>
                  {REASONS.map((r) => (
                    <option key={r.value} value={r.value}>
                      {r.label}
                    </option>
                  ))}
                </Select>
              </div>
              <div>
                <Label htmlFor={`rep-details-${id}`}>Details (optional)</Label>
                <Textarea id={`rep-details-${id}`} value={details} onChange={(e) => setDetails(e.target.value)} maxLength={500} className="min-h-20" />
                <FieldHint>Only admins see this. Don't include passwords or payment details.</FieldHint>
              </div>
              <div className="flex justify-end">
                <Button type="submit" variant="primary" loading={send.isPending} disabled={!reason}>
                  Send report
                </Button>
              </div>
            </form>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
