// Help, for the Creator Studio and the Brand Console: the basics, connected apps (creators),
// and account management (deleting the account lives here; signing out stays in the menu).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, Instagram, LifeBuoy, Sparkles, UserRound, Youtube } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { DeleteAccountButton } from "@/components/shared/AccountMenu";
import { ChangePassword, DownloadData, EmailStatus, SignedInDevices } from "@/components/shared/AccountSecurity";
import { useAiAssistant } from "@/components/shared/AiAssistant";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/overlays";
import { api, post } from "@/lib/api";
import { useCreatorId, useSession } from "@/lib/session";
import type { LinkedYouTube, PlatformStatus } from "@/lib/youtube-types";

type Role = "creator" | "brand";
type QA = { q: string; a: string };

const BASICS: Record<Role, QA[]> = {
  creator: [
    {
      q: "How does DealMeet work?",
      a: "Home gives you 3 moves for the week, built from your own numbers. Money shows your fair price for a brand post. Opportunities lists campaigns that fit you, and every deal is paid into escrow before you post, then released when the brand approves your post.",
    },
    {
      q: "How is my price worked out?",
      a: "From the views your recent posts get (not your follower count), times your niche's rate per 1,000 views, with small, capped adjustments for engagement, consistency, brand safety and trust. When AI is on, an AI market review can move it by -30% to +40%, with its reasons. Money shows every step.",
    },
    {
      q: "How and when do I get paid?",
      a: "The brand pays into escrow when the contract is signed. You post and submit the link; the brand approves it (or it's approved automatically after the review window), and the money is released to you. Deals shows where each one is.",
    },
    {
      q: "What do Live data, Self-reported and Sample data mean?",
      a: "Live data comes from your connected YouTube or Instagram. Self-reported is what you typed in. Sample data is only in the demo. Every number in DealMeet carries one of these labels.",
    },
    {
      q: "What do brands see about me?",
      a: "What you choose under Privacy: your stats, your audience, your rate card. You can change it anytime, and each brand's access is listed there.",
    },
    {
      q: "How do I use DealMeet AI?",
      a: "Type into the bar at the bottom of any page, or press Ctrl J (⌘ J on a Mac). Ask about your numbers, get advice, or ask it to draft a pitch or make a plan. It asks before sending anything.",
    },
  ],
  brand: [
    {
      q: "How does DealMeet work for brands?",
      a: "Post a campaign, and DealMeet ranks creators by how well their real audience fits yours, with a fair price for each. Shortlist, send offers, and pay into escrow; the money is released when you approve the creator's post.",
    },
    {
      q: "How are creators priced?",
      a: "On the views their recent posts get, not their follower count, times their niche's rate per 1,000 views, with capped adjustments for engagement, audience fit to your brand, consistency, brand safety and trust. Each creator's page shows every step.",
    },
    {
      q: "How does escrow protect me?",
      a: "You pay into escrow when the contract is signed. The creator is paid only after you approve their post, or after the review window if you don't respond. Deals shows every step and its date.",
    },
    {
      q: "What can I see about a creator?",
      a: "What they choose to share with brands: their stats, audience and rate card. Anything they haven't shared stays hidden, and their match is worked out without it.",
    },
    {
      q: "What is the Fan Inbox?",
      a: "Pitches from creators who already post about your brand, with proof from their own posts. Reply, or turn one into an offer.",
    },
    {
      q: "How do I use DealMeet AI?",
      a: "Type into the bar at the bottom of any page, or press Ctrl J (⌘ J on a Mac). Ask how your campaigns are doing, or ask it to draft a brief or an offer. It asks before publishing or sending anything.",
    },
  ],
};

const APPS: QA[] = [
  {
    q: "How does DealMeet get my numbers?",
    a: "From the apps you sign in with or connect, through YouTube's and Instagram's official APIs. Signing in with YouTube also brings in YouTube Analytics. We never ask for your password and never scrape.",
  },
  {
    q: "What can DealMeet see, and what can't it do?",
    a: "Read-only: your channel's or account's numbers, your posts' views and engagement, and your audience's age, gender and country. We can't post, comment, upload or change anything on your accounts.",
  },
  {
    q: "What do the coloured dots on Connections mean?",
    a: "Green: live, your numbers are up to date. Amber: the app's access has run out, so reconnect it. Red: the last update failed; it usually passes, and Refresh or Sync now tries again. Grey: not connected.",
  },
  {
    q: "How do I refresh my numbers?",
    a: "YouTube: press Refresh on Connections, or sign in again with Continue with YouTube (that also refreshes Analytics). Instagram updates on its own every day; Sync now updates it right away.",
  },
  {
    q: "My niche, language or city is wrong.",
    a: "Change it in Profile. Your price, matches and moves update straight away. If your niche was read from your titles, the AI can get it wrong for mixed channels.",
  },
  {
    q: "Analytics didn't connect, or my channel isn't found.",
    a: "Sign in with the Google account that owns the channel. For a brand account on YouTube, choose the brand account in Google's window. While DealMeet's Google app is in testing, your Google account must be on its test-user list.",
  },
];

function Item({ q, children }: { q: string; children: ReactNode }) {
  return (
    <details className="group">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3.5 text-sm font-medium hover:bg-surface-2 [&::-webkit-details-marker]:hidden">
        {q}
        <ChevronDown className="size-4 shrink-0 text-muted transition-transform group-open:rotate-180" aria-hidden />
      </summary>
      <div className="px-4 pb-4 text-sm leading-relaxed text-fg-2">{children}</div>
    </details>
  );
}

function Group({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section aria-labelledby={id} className="mt-8">
      <h2 id={id} className="text-xs font-semibold text-muted">
        {title}
      </h2>
      <div className="mt-3 divide-y divide-line overflow-hidden rounded-[var(--radius-card)] border border-line bg-surface">{children}</div>
    </section>
  );
}

export default function HelpCenter({ role }: { role: Role }) {
  const ai = useAiAssistant();
  const user = useSession(role).data?.user;
  const base = role === "creator" ? "/creator" : "/brand";
  return (
    <div>
      <p className="flex items-center gap-1.5 text-xs font-medium text-accent">
        <LifeBuoy className="size-3.5" aria-hidden /> Help
      </p>
      <h1 className="mt-1 font-display text-[26px] font-semibold tracking-tight sm:text-[30px]">How can we help?</h1>
      <p className="mt-1 max-w-2xl text-[15px] text-fg-2">Answers to common questions, your connected apps and your account.</p>

      {ai && (
        <div className="mt-6 flex flex-wrap items-center gap-3 rounded-[var(--radius-card)] border border-line bg-surface-2 p-4">
          <span className="grid size-9 place-items-center rounded-xl bg-surface-3 text-accent">
            <Sparkles className="size-4" aria-hidden />
          </span>
          <p className="min-w-0 flex-1 text-sm text-fg-2">
            <span className="font-medium text-fg">Ask DealMeet AI.</span> It knows your {role === "creator" ? "numbers" : "campaigns"} and answers in your language.
          </p>
          <Button size="sm" variant="primary" onClick={() => ai.open()}>
            Ask a question
          </Button>
        </div>
      )}

      <Group id="h-basics" title="Getting started">
        {BASICS[role].map((x) => (
          <Item key={x.q} q={x.q}>
            {x.a}
          </Item>
        ))}
      </Group>

      {role === "creator" && <ConnectedApps />}

      <Group id="h-account" title="Your account">
        <Item q={role === "creator" ? "Change your name, niche, city or languages" : "Change your brand's details"}>
          <p>{role === "creator" ? "Edit them in Profile. Your price, matches and moves update straight away." : "Edit your category, audience, budget and website in Brand profile."}</p>
          <Link to={`${base}/profile`} className="mt-2 inline-flex items-center gap-1.5 font-medium text-accent underline-offset-4 hover:underline">
            <UserRound className="size-3.5" aria-hidden /> Open {role === "creator" ? "Profile" : "Brand profile"}
          </Link>
        </Item>
        {role === "creator" && (
          <Item q="Privacy: what brands can see">
            <p>Choose what brands can see: your stats, your audience and your rate card.</p>
            <Link to="/creator/privacy" className="mt-2 inline-block font-medium text-accent underline-offset-4 hover:underline">
              Open Privacy
            </Link>
          </Item>
        )}
        <Item q="Signing in and out">
          <p>
            {user?.email ? `You're signed in as ${user.email}. ` : ""}Sign out from the menu under your name at the top of the sidebar (More on a phone). Signing out ends this
            session on this device; Signed-in devices below can sign out the others.
          </p>
        </Item>
        {!user?.demo && (
          <>
            <Item q="Signed-in devices">
              <p className="mb-3">Each place you're signed in. If you don't recognise one, sign it out and change your password.</p>
              <SignedInDevices role={role} />
            </Item>
            {user?.providers.includes("password") && (
              <Item q="Change your password">
                <ChangePassword role={role} />
              </Item>
            )}
            {user?.email && (
              <Item q="Your email address">
                <EmailStatus role={role} />
              </Item>
            )}
          </>
        )}
        <Item q="Download your data">
          <p className="mb-3">
            One file with everything DealMeet holds that's tied to your account: your profile, {role === "creator" ? "deals, rates, media kits, pitches, connected-app numbers and consents" : "campaigns, deals, shortlists and offers"}, your
            signed-in devices and your activity log. Passwords and app tokens are never included.
          </p>
          <DownloadData role={role} />
        </Item>
        <Item q="Delete your account">
          {user?.demo ? (
            <p>Demo profiles can't be deleted: they reset to sample data.</p>
          ) : (
            <>
              <p>
                This deletes your account and everything that's only yours, and signs you out everywhere. Deals with work or money in progress need to be finished or
                cancelled first. You'll be asked to type DELETE to confirm.
              </p>
              <DeleteAccountButton role={role} className="mt-3 w-auto" />
            </>
          )}
        </Item>
      </Group>
    </div>
  );
}

// ------------------------------------------------------------------ connected apps (creators)
function ConnectedApps() {
  const id = useCreatorId();
  const q = useQuery({ queryKey: ["connections", id], queryFn: () => api<{ platforms: PlatformStatus[] }>(`/creators/${id}/connections`) });
  const by = Object.fromEntries((q.data?.platforms ?? []).map((p) => [p.platform, p]));
  return (
    <Group id="h-apps" title="Connected apps">
      {APPS.map((x) => (
        <Item key={x.q} q={x.q}>
          {x.a}
        </Item>
      ))}
      <Item q="Remove an app's access">
        <p>Removing access disconnects the app and deletes the numbers DealMeet stored from it. Your profile stays; you can connect again anytime.</p>
        {by.youtube && by.instagram && <RemoveAccess creatorId={id} youtube={by.youtube} instagram={by.instagram} />}
      </Item>
    </Group>
  );
}

type Removal = "youtube" | "analytics" | "instagram";

const REMOVE: Record<Removal, { title: string; what: string; button: string }> = {
  youtube: {
    title: "Remove YouTube access?",
    what: "DealMeet disconnects your channel and deletes its videos, Analytics and snapshots. Your price and dashboard go back to what you typed in.",
    button: "Yes, remove YouTube",
  },
  analytics: {
    title: "Remove YouTube Analytics?",
    what: "DealMeet deletes your Analytics: watch time and your audience's age, gender and country. Your channel stays connected.",
    button: "Yes, remove Analytics",
  },
  instagram: {
    title: "Remove Instagram access?",
    what: "DealMeet deletes its Instagram access and every post, insight and audience number it stored.",
    button: "Yes, remove Instagram",
  },
};

function RemoveAccess({ creatorId, youtube, instagram }: { creatorId: string; youtube: PlatformStatus; instagram: PlatformStatus }) {
  const qc = useQueryClient();
  const [ask, setAsk] = useState<Removal | null>(null);
  const yt = useQuery({ queryKey: ["youtube", creatorId], queryFn: () => api<LinkedYouTube>(`/creators/${creatorId}/youtube`), enabled: youtube.status !== "unavailable" });
  const remove = useMutation({
    mutationFn: (what: Removal) =>
      what === "youtube"
        ? api(`/creators/${creatorId}/youtube/link`, { method: "DELETE" })
        : what === "analytics"
          ? api("/connect/youtube/analytics", { method: "DELETE" })
          : post("/connect/instagram/disconnect"),
    onSuccess: (_, what) => {
      setAsk(null);
      void qc.invalidateQueries();
      toast.success(what === "analytics" ? "YouTube Analytics removed" : `${what === "youtube" ? "YouTube" : "Instagram"} access removed`);
    },
    onError: (e) => toast.error((e as Error).message),
  });
  const ytOn = !!yt.data?.linked;
  const igOn = instagram.status === "connected" || instagram.status === "expired" || instagram.status === "error";
  if (!ytOn && !igOn) return <p className="mt-3 text-muted">No apps are connected.</p>;
  return (
    <>
      <div className="mt-3 flex flex-wrap gap-2">
        {ytOn && (
          <Button size="sm" variant="danger" onClick={() => setAsk("youtube")}>
            <Youtube aria-hidden /> Remove YouTube access
          </Button>
        )}
        {ytOn && yt.data?.analytics && (
          <Button size="sm" variant="outline" onClick={() => setAsk("analytics")}>
            Remove only Analytics
          </Button>
        )}
        {igOn && (
          <Button size="sm" variant="danger" onClick={() => setAsk("instagram")}>
            <Instagram aria-hidden /> Remove Instagram access
          </Button>
        )}
      </div>
      <Dialog open={!!ask} onOpenChange={(v) => !v && setAsk(null)}>
        {ask && (
          <DialogContent title={REMOVE[ask].title} description="Are you sure? This can't be undone, but you can connect again later.">
            <p className="text-sm leading-relaxed text-fg-2">{REMOVE[ask].what}</p>
            <div className="mt-5 flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setAsk(null)}>
                Keep it
              </Button>
              <Button variant="danger" loading={remove.isPending} onClick={() => remove.mutate(ask)}>
                {REMOVE[ask].button}
              </Button>
            </div>
          </DialogContent>
        )}
      </Dialog>
    </>
  );
}
