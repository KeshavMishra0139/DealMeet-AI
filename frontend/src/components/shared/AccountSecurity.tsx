// Account security, in Help → Your account: the devices signed in to this account (sign one
// out, or all the others), changing the password, and confirming the email address. The
// server keeps a coarse device label per session ("Chrome on Android"), never an IP address.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Laptop, MailCheck, MailWarning, Smartphone, X } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { ErrorState } from "@/components/shared/Bits";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { FieldHint, Input, Label, Skeleton } from "@/components/ui/form";
import { api } from "@/lib/api";
import { shortDate, timeOfDay } from "@/lib/format";
import { useSession, type Role } from "@/lib/session";
import { useHealth } from "@/lib/shared-demo";
import { safeStorage } from "@/lib/utils";

interface Device {
  id: string;
  device: string;
  via: string | null;
  created_at: number;
  last_used: number;
  current: boolean;
}

const VIA: Record<string, string> = {
  password: "email and password",
  password_reset: "a password reset",
  "firebase:google.com": "Google",
  "firebase:phone": "phone",
  instagram: "Instagram",
  youtube: "YouTube",
  demo: "the demo",
};

function when(seconds: number) {
  const iso = new Date(seconds * 1000).toISOString();
  return `${shortDate(iso)}, ${timeOfDay(iso)}`;
}

/** The devices signed in to this account, this one first. */
export function SignedInDevices({ role }: { role: Role }) {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["sessions", role], queryFn: () => api<{ items: Device[] }>("/auth/sessions", { role }) });
  const done = (message: string) => {
    toast.success(message);
    void qc.invalidateQueries({ queryKey: ["sessions", role] });
  };
  const one = useMutation({
    mutationFn: (id: string) => api(`/auth/sessions/${id}/revoke`, { method: "POST", role }),
    onSuccess: () => done("That device is signed out"),
    onError: (e) => toast.error((e as Error).message),
  });
  const others = useMutation({
    mutationFn: () => api<{ revoked: number }>("/auth/sessions/revoke-others", { method: "POST", role }),
    onSuccess: (r) => done(r.revoked === 1 ? "1 other device is signed out" : `${r.revoked} other devices are signed out`),
    onError: (e) => toast.error((e as Error).message),
  });
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data) return <Skeleton className="h-24 rounded-xl" />;
  const items = q.data.items;
  return (
    <div>
      <ul className="divide-y divide-line rounded-xl border border-line" aria-label="Signed-in devices">
        {items.map((d) => {
          const Icon = /Android|iPhone/.test(d.device) ? Smartphone : Laptop;
          return (
            <li key={d.id} className="flex flex-wrap items-center gap-x-3 gap-y-1.5 px-3 py-2.5">
              <Icon className="size-4 shrink-0 text-muted" aria-hidden />
              <div className="min-w-0 flex-1">
                <p className="flex flex-wrap items-center gap-2 text-sm font-medium text-fg">
                  {d.device} {d.current && <Badge size="sm" variant="accent">This device</Badge>}
                </p>
                <p className="text-xs text-muted">
                  Signed in with {VIA[d.via ?? ""] ?? "another method"} on {when(d.created_at)} · last used {when(d.last_used)}
                </p>
              </div>
              {!d.current && (
                <Button size="sm" variant="ghost" loading={one.isPending && one.variables === d.id} onClick={() => one.mutate(d.id)} aria-label={`Sign out ${d.device}`}>
                  Sign out
                </Button>
              )}
            </li>
          );
        })}
      </ul>
      {items.some((d) => !d.current) && (
        <Button size="sm" variant="outline" className="mt-3" loading={others.isPending} onClick={() => others.mutate()}>
          Sign out everywhere else
        </Button>
      )}
    </div>
  );
}

/** Change the password; every other device is signed out. Only for email-and-password accounts. */
export function ChangePassword({ role }: { role: Role }) {
  const qc = useQueryClient();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const change = useMutation({
    mutationFn: () => api("/auth/password", { method: "POST", json: { current, new: next }, role }),
    onSuccess: () => {
      setCurrent("");
      setNext("");
      toast.success("Your password is changed", { description: "Every other device was signed out." });
      void qc.invalidateQueries({ queryKey: ["sessions", role] });
    },
  });
  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        change.mutate();
      }}
    >
      <div>
        <Label htmlFor="pw-current">Current password</Label>
        <Input id="pw-current" type="password" value={current} onChange={(e) => setCurrent(e.target.value)} required autoComplete="current-password" maxLength={128} />
      </div>
      <div>
        <Label htmlFor="pw-new">New password</Label>
        <Input id="pw-new" type="password" value={next} onChange={(e) => setNext(e.target.value)} required minLength={8} maxLength={128} autoComplete="new-password" />
        <FieldHint>At least 8 characters. Changing it signs you out on every other device.</FieldHint>
      </div>
      {change.isError && (
        <p role="alert" className="text-sm text-danger">
          {(change.error as Error).message}
        </p>
      )}
      <Button type="submit" size="sm" variant="primary" loading={change.isPending} disabled={!current || next.length < 8}>
        Change password
      </Button>
    </form>
  );
}

/** Whether the account's email is confirmed, with a button to send the link again. */
export function EmailStatus({ role }: { role: Role }) {
  const user = useSession(role).data?.user;
  const emailOn = useHealth().data?.modes.email === "smtp";
  const resend = useMutation({
    mutationFn: () => api<{ sent_to: string }>("/auth/email/resend", { method: "POST", role }),
    onSuccess: (r) => toast.success(`We sent a link to ${r.sent_to}`, { description: "It works for 48 hours." }),
    onError: (e) => toast.error((e as Error).message),
  });
  if (!user?.email) return <p>This account signs in without an email address.</p>;
  if (user.email_verified)
    return (
      <p className="flex items-center gap-2">
        <MailCheck className="size-4 shrink-0 text-success" aria-hidden /> {user.email} is confirmed.
      </p>
    );
  return (
    <div>
      <p className="flex items-start gap-2">
        <MailWarning className="mt-0.5 size-4 shrink-0 text-warn" aria-hidden />
        <span>
          {user.email} isn't confirmed yet.{" "}
          {emailOn ? "Open the link we emailed you, or send a new one." : "Email isn't set up on this server yet, so there's nothing to do for now."}
        </span>
      </p>
      {emailOn && (
        <Button size="sm" variant="outline" className="mt-3" loading={resend.isPending} onClick={() => resend.mutate()}>
          Send the link again
        </Button>
      )}
    </div>
  );
}

/** Download my data: every record tied to the account, as a JSON file to keep. */
export function DownloadData({ role }: { role: Role }) {
  const download = useMutation({
    mutationFn: () => api<Record<string, unknown>>("/auth/export", { role }),
    onSuccess: (data) => {
      const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `dealmeet-data-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      toast.success("Your data is downloading");
    },
    onError: (e) => toast.error((e as Error).message),
  });
  return (
    <Button size="sm" variant="outline" loading={download.isPending} onClick={() => download.mutate()}>
      <Download aria-hidden /> Download my data
    </Button>
  );
}

const NUDGE_KEY = "jd.email-nudge.hidden";

/** A one-line reminder at the top of the Studio and Console while the account's email isn't
 * confirmed and email is set up. Hidden for this browser once closed. */
export function EmailNudge({ role }: { role: Role }) {
  const user = useSession(role).data?.user;
  const emailOn = useHealth().data?.modes.email === "smtp";
  const store = safeStorage();
  const [hidden, setHidden] = useState(() => store.get(NUDGE_KEY) === user?.id);
  if (!user?.email || user.email_verified || user.demo || !emailOn || hidden) return null;
  return (
    <div role="note" className="mb-5 flex items-center gap-3 rounded-xl border border-warn/40 bg-warn-soft px-3 py-2 text-sm">
      <MailWarning className="size-4 shrink-0 text-warn" aria-hidden />
      <p className="min-w-0 flex-1">
        Confirm {user.email} with the link we emailed you.{" "}
        <Link to={`/${role}/help`} className="font-medium underline underline-offset-4">
          Send it again
        </Link>
      </p>
      <button
        type="button"
        aria-label="Hide this reminder"
        className="rounded-md p-1 text-muted hover:bg-surface-2 hover:text-fg"
        onClick={() => {
          store.set(NUDGE_KEY, user.id);
          setHidden(true);
        }}
      >
        <X className="size-4" aria-hidden />
      </button>
    </div>
  );
}
