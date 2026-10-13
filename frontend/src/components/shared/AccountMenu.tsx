// The account menu at the top of the Studio and Console sidebars: who's signed in, links to
// the account's settings, Sign out and Delete account. Deleting needs the word DELETE typed,
// and the server refuses while a deal has work or money in progress (services/account.py).
import { useQueryClient } from "@tanstack/react-query";
import { ChevronDown, LogOut, Trash2 } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/form";
import { Dialog, DialogContent, Popover, PopoverContent, PopoverTrigger } from "@/components/ui/overlays";
import { api, ApiError } from "@/lib/api";
import { forgetAllTokens, pinnedPersona, useSession, type Role } from "@/lib/session";
import { cn } from "@/lib/utils";
import { useSignOut } from "./AuthGate";

const PROVIDER: Record<string, string> = { password: "email and password", firebase: "Google", youtube: "YouTube", instagram: "Instagram" };

function signedInWith(user: { email: string | null; providers: string[] }) {
  const via = user.providers.map((p) => PROVIDER[p] ?? p).filter(Boolean);
  return [user.email, via.length ? `Signed in with ${via.join(", ")}` : null].filter(Boolean).join(" · ");
}

/** Whether this tab's account can be deleted here (not a demo profile). */
function useDeletable(role: Role) {
  const user = useSession(role).data?.user;
  return !!user && !user.demo && !pinnedPersona(role);
}

export function AccountMenu({ role, links, children, className }: { role: Role; links: { label: string; to: string }[]; children: ReactNode; className?: string }) {
  const user = useSession(role).data?.user;
  const signOut = useSignOut(role);
  const deletable = useDeletable(role);
  const [open, setOpen] = useState(false);
  const [confirm, setConfirm] = useState(false);
  return (
    <>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <button type="button" aria-label={`${user?.name ?? "Your account"}, account menu`} className={cn("group relative block w-full rounded-2xl text-left", className)}>
            {children}
            <ChevronDown aria-hidden className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-muted transition-transform group-data-[state=open]:rotate-180" />
          </button>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-72 p-2">
          {user && (
            <div className="px-2.5 pb-2 pt-1.5">
              <p className="truncate text-sm font-semibold">{user.name ?? "Your account"}</p>
              <p className="mt-0.5 text-xs leading-snug text-muted">{user.demo ? "Demo profile: sample data that resets." : signedInWith(user)}</p>
            </div>
          )}
          <div className="border-t border-line pt-1.5">
            {links.map((l) => (
              <Link key={l.to} to={l.to} onClick={() => setOpen(false)} className="block rounded-lg px-2.5 py-2 text-sm hover:bg-surface-2">
                {l.label}
              </Link>
            ))}
          </div>
          {!pinnedPersona(role) && (
            <div className="mt-1.5 border-t border-line pt-1.5">
              <button
                type="button"
                className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-sm hover:bg-surface-2"
                onClick={() => {
                  setOpen(false);
                  void signOut.run();
                }}
              >
                <LogOut className="size-4" aria-hidden /> Sign out
              </button>
              {deletable && (
                <button
                  type="button"
                  className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-sm text-danger hover:bg-surface-2"
                  onClick={() => {
                    setOpen(false);
                    setConfirm(true);
                  }}
                >
                  <Trash2 className="size-4" aria-hidden /> Delete account
                </button>
              )}
            </div>
          )}
        </PopoverContent>
      </Popover>
      <DeleteAccountDialog role={role} open={confirm} onOpenChange={setConfirm} />
    </>
  );
}

/** Delete account in the mobile menu and sidebar controls; hidden for demo profiles. */
export function DeleteAccountButton({ role, className, size = "sm" }: { role: Role; onDone?: () => void; className?: string; size?: "sm" | "md" }) {
  const deletable = useDeletable(role);
  const [open, setOpen] = useState(false);
  if (!deletable) return null;
  return (
    <>
      <Button
        variant="ghost"
        size={size}
        className={cn("w-full justify-start text-danger", className)}
        // The confirmation opens over the menu this button sits in; closing that menu first
        // (onDone) would unmount the confirmation with it. Cancel returns to the menu.
        onClick={() => setOpen(true)}
      >
        <Trash2 aria-hidden /> Delete account
      </Button>
      <DeleteAccountDialog role={role} open={open} onOpenChange={setOpen} />
    </>
  );
}

function DeleteAccountDialog({ role, open, onOpenChange }: { role: Role; open: boolean; onOpenChange: (open: boolean) => void }) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [word, setWord] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const what =
    role === "creator"
      ? "Your profile, connected YouTube and Instagram data, rates, media kit, pitches, plans and applications."
      : "Your brand page, campaigns, shortlists, drafts and applications to your campaigns.";
  const run = async () => {
    setBusy(true);
    setError("");
    try {
      await api("/auth/delete-account", { method: "POST", json: { confirm: "DELETE" }, role });
      forgetAllTokens();
      qc.clear();
      onOpenChange(false);
      toast.success("Your account was deleted");
      navigate("/", { replace: true });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't delete the account. Try again.");
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) {
          setWord("");
          setError("");
        }
        onOpenChange(o);
      }}
    >
      <DialogContent title="Delete your account" description="This can't be undone.">
        <p className="text-sm leading-relaxed text-fg-2">
          This deletes your account and signs you out everywhere. Deleted with it: {what} Paid deals stay in the other side's records.
        </p>
        <p className="mt-2 text-sm leading-relaxed text-fg-2">Deals with work or money in progress need to be finished or cancelled first.</p>
        <div className="mt-4">
          <Label htmlFor="delete-word">Type DELETE to confirm</Label>
          <Input id="delete-word" value={word} onChange={(e) => setWord(e.target.value)} autoComplete="off" />
        </div>
        {error && (
          <p role="alert" className="mt-2 text-sm text-danger">
            {error}
          </p>
        )}
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button variant="danger" disabled={word !== "DELETE"} loading={busy} onClick={() => void run()}>
            Delete account
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
