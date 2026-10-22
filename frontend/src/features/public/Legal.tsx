// /privacy and /terms. The text describes what this code does (services/retention.py,
// data_export.py, consent.py, the sign-in and platform integrations); change it when the
// code changes. Who runs the site comes from the server's settings (GET /api/legal); a
// detail that isn't set says so instead of showing a made-up one. Have a lawyer review both
// before launch.
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Wordmark } from "@/components/shared/Wordmark";
import { api } from "@/lib/api";
import { useTheme } from "@/lib/theme";

const UPDATED = "22 October 2026";

interface Operator {
  name: string | null;
  address: string | null;
  contact_email: string | null;
  grievance: { name: string | null; email: string | null };
  city: string | null;
}

function useOperator() {
  return useQuery({ queryKey: ["legal"], queryFn: () => api<Operator>("/legal", { role: null }), staleTime: 3_600_000 }).data;
}

function Missing() {
  return <span className="rounded bg-warn-soft px-1 text-fg">not published yet</span>;
}

function Value({ v, email = false }: { v: string | null | undefined; email?: boolean }) {
  if (!v) return <Missing />;
  return email ? (
    <a href={`mailto:${v}`} className="font-medium text-accent underline-offset-4 hover:underline">
      {v}
    </a>
  ) : (
    <>{v}</>
  );
}

function Page({ title, intro, children }: { title: string; intro: ReactNode; children: ReactNode }) {
  useTheme("site");
  return (
    <div className="theme-site min-h-dvh bg-[#f9fafb] text-[#0a1b33]">
      <header className="mx-auto flex max-w-3xl items-center justify-between px-4 py-5 sm:px-6">
        <Link to="/" aria-label="DealMeet AI home">
          <Wordmark />
        </Link>
        <Link to="/" className="inline-flex items-center gap-1.5 text-sm text-slate-600 hover:text-[#0a1b33]">
          <ArrowLeft className="size-4" aria-hidden /> Home
        </Link>
      </header>
      <main id="main" className="mx-auto max-w-3xl px-4 pb-20 sm:px-6">
        <h1 className="font-display text-3xl font-semibold tracking-tight sm:text-4xl">{title}</h1>
        <p className="mt-2 text-sm text-slate-600">Last updated {UPDATED}</p>
        <div className="mt-6 text-[15px] leading-relaxed text-slate-700">{intro}</div>
        <div className="legal mt-8 space-y-8 text-[15px] leading-relaxed text-slate-700 [&_h2]:font-display [&_h2]:text-xl [&_h2]:font-semibold [&_h2]:text-[#0a1b33] [&_li]:mt-1.5 [&_p]:mt-3 [&_ul]:mt-3 [&_ul]:list-disc [&_ul]:pl-5">
          {children}
        </div>
        <p className="mt-12 text-sm text-slate-600">
          See also the <Link to={title === "Privacy Policy" ? "/terms" : "/privacy"} className="font-medium text-accent hover:underline">{title === "Privacy Policy" ? "Terms of Use" : "Privacy Policy"}</Link>.
        </p>
      </main>
    </div>
  );
}

function Contact({ o }: { o: Operator | undefined }) {
  return (
    <ul>
      <li>
        Operator: <Value v={o?.name} />
        {o?.address ? `, ${o.address}` : ""}
      </li>
      <li>
        Questions about your data: <Value v={o?.contact_email} email />
      </li>
      <li>
        Grievance Officer: <Value v={o?.grievance.name} />, <Value v={o?.grievance.email} email />.
      </li>
    </ul>
  );
}

export function PrivacyPolicy() {
  const o = useOperator();
  return (
    <Page
      title="Privacy Policy"
      intro={
        <section aria-labelledby="in-short" className="rounded-2xl border border-slate-200 bg-white p-5">
          <h2 id="in-short" className="font-display text-lg font-semibold text-[#0a1b33]">
            In short
          </h2>
          <ul className="mt-3 list-disc space-y-1.5 pl-5">
            <li>We use your data to run DealMeet AI: your profile, your prices, matches with brands, deals and payments. We don't sell it and there are no ad trackers.</li>
            <li>Brands see only what you choose to share (your stats, audience and rate card), and you can change that at any time under Privacy.</li>
            <li>Connected YouTube and Instagram accounts are read-only, through their official APIs. We never ask for your passwords and never scrape.</li>
            <li>You can download everything we hold about your account, and delete your account, from Help → Your account.</li>
            <li>Passwords are stored only as hashes; app tokens are encrypted; old records are deleted on a fixed schedule (below).</li>
          </ul>
        </section>
      }
    >
      <section>
        <h2>Who we are</h2>
        <p>DealMeet AI connects Indian creators with brands. This policy explains what personal data we collect, why, who we share it with, how long we keep it and your rights under India's Digital Personal Data Protection Act, 2023.</p>
        <Contact o={o} />
      </section>

      <section>
        <h2>What we collect</h2>
        <ul>
          <li><strong>Your account:</strong> name, email, a hash of your password (never the password), your phone number if you sign in by phone, whether you're a creator or a brand, and the IDs of the Google, Instagram or YouTube accounts you sign in with.</li>
          <li><strong>Creator profiles:</strong> what you enter (niche, city, languages, bio, follower counts, rates) and, if you connect them, numbers from YouTube and Instagram: channel and account details, posts and their views and engagement, reach, and audience age, gender and location as totals (never individual followers).</li>
          <li><strong>Brand profiles:</strong> brand name, category, website, audience, budget and campaigns. Brand pages that aren't claimed list only public facts with their sources.</li>
          <li><strong>Deals:</strong> offers, contracts and their versions, deliverables, post links and checks, invoices, and payment records (order IDs, amounts and statuses; card and bank details are handled by Razorpay, not us).</li>
          <li><strong>Conversations with DealMeet AI</strong> and the drafts it writes for you.</li>
          <li><strong>Security records:</strong> your signed-in devices (a label like "Chrome on Android" and when each was last used), an activity log of sign-ins and changes, and short-lived counters that limit repeated attempts. IP addresses appear only in those counters, which are deleted within hours.</li>
          <li><strong>Emails we send you</strong>: who, what kind and when (never the message itself).</li>
        </ul>
        <p>In your browser we keep one sign-in cookie (HttpOnly, so scripts can't read it) and a few preferences in local storage: your language, a dismissed reminder and, in the demo only, demo sign-ins. There are no advertising or analytics cookies.</p>
      </section>

      <section>
        <h2>Why we use it</h2>
        <ul>
          <li>To run your account and keep it secure, including detecting abuse.</li>
          <li>To work out fair prices, plans and matches from your own numbers. Prices are estimates, not offers.</li>
          <li>To show brands what you have chosen to share, and to tell you who has looked.</li>
          <li>To run deals: contracts, escrow payments, post checks and invoices.</li>
          <li>To send emails you need: sign-in and password links, and notices about your account.</li>
          <li>To meet legal duties, such as keeping security logs and financial records.</li>
        </ul>
        <p>We use your data because you consent to it (for example when you connect an account or share data with a brand) or because it's needed to provide the service you asked for. You can withdraw consent at any time; it doesn't affect what was done before.</p>
      </section>

      <section>
        <h2>Who we share it with</h2>
        <ul>
          <li><strong>Brands</strong>, only what you allow under Privacy, and the details of deals you make with them.</li>
          <li><strong>Service providers</strong> who process data for us: hosting (Render, in Singapore), our database (MongoDB Atlas), sign-in (Google Firebase), payments (Razorpay), email delivery, and, when AI is switched on, an AI model provider (Anthropic, directly or through OpenRouter) for the parts of your data a request needs.</li>
          <li><strong>Google (YouTube) and Meta (Instagram)</strong>, when you connect those accounts, under their own terms.</li>
          <li><strong>Authorities</strong>, when the law requires it.</li>
        </ul>
        <p>Some of these providers store data outside India. We don't sell personal data.</p>
      </section>

      <section>
        <h2>YouTube and Instagram</h2>
        <p>
          DealMeet AI uses YouTube API Services. By connecting YouTube you also agree to the{" "}
          <a href="https://www.youtube.com/t/terms" className="text-accent underline underline-offset-2" rel="noreferrer" target="_blank">YouTube Terms of Service</a>, and Google's handling of your data is described in the{" "}
          <a href="https://policies.google.com/privacy" className="text-accent underline underline-offset-2" rel="noreferrer" target="_blank">Google Privacy Policy</a>. You can remove DealMeet's access at{" "}
          <a href="https://security.google.com/settings/security/permissions" className="text-accent underline underline-offset-2" rel="noreferrer" target="_blank">Google's security settings</a>. YouTube data we haven't refreshed in 30 days is hidden.
        </p>
        <p>Instagram access is read-only through Meta's official login. Disconnecting in DealMeet, or removing DealMeet in Instagram's settings, deletes the token and the Instagram data we stored. You can also send a data deletion request through Instagram; you'll get a confirmation code and a page showing it's done.</p>
      </section>

      <section>
        <h2>How long we keep it</h2>
        <ul>
          <li>Your account and profile: until you delete your account.</li>
          <li>Sign-ins: until they expire, or 30 days after you sign out. Sign-in, reset and confirmation links: until they expire (15 minutes to 48 hours).</li>
          <li>The activity log and the email log: one year (Indian rules ask for security logs to be kept at least 180 days).</li>
          <li>Records of what you consented to, and deals, invoices and payment records: kept after you delete your account, because the other side of a deal and the law rely on them.</li>
          <li>Unsubscribes: kept, so we keep honouring them.</li>
        </ul>
      </section>

      <section>
        <h2>Your rights</h2>
        <ul>
          <li><strong>See your data:</strong> Help → Your account → Download your data gives you one file with everything tied to your account.</li>
          <li><strong>Correct it:</strong> edit your profile at any time, or ask us.</li>
          <li><strong>Delete it:</strong> Help → Your account → Delete your account. Deals with work or money in progress need finishing first.</li>
          <li><strong>Withdraw consent:</strong> change what brands see under Privacy, or disconnect YouTube or Instagram.</li>
          <li><strong>Nominate someone</strong> to exercise these rights if you die or can't: write to the Grievance Officer.</li>
          <li><strong>Complain:</strong> to our Grievance Officer first; if you're not satisfied, to the Data Protection Board of India.</li>
        </ul>
      </section>

      <section>
        <h2>Security</h2>
        <p>Connections are encrypted (HTTPS). Passwords are hashed with scrypt; Instagram tokens and admin sign-in secrets are encrypted at rest. Admins must use two-step sign-in, and every admin action is logged with its reason. If a breach affects your data, we'll tell you and the Data Protection Board as the law requires.</p>
      </section>

      <section>
        <h2>Children</h2>
        <p>DealMeet AI is for people aged 18 and over. We don't knowingly collect data from children; if you think a child has an account, contact us and we'll remove it.</p>
      </section>

      <section>
        <h2>Changes</h2>
        <p>We'll update the date at the top when this policy changes, and tell you by email or in the app before a change that affects how we use your data.</p>
      </section>
    </Page>
  );
}

export function TermsOfUse() {
  const o = useOperator();
  return (
    <Page
      title="Terms of Use"
      intro={
        <p>
          These terms are an agreement between you and <Value v={o?.name} /> ("we") for using DealMeet AI. By creating an account you accept them and our{" "}
          <Link to="/privacy" className="font-medium text-accent hover:underline">Privacy Policy</Link>.
        </p>
      }
    >
      <section>
        <h2>Your account</h2>
        <ul>
          <li>You must be 18 or older and give accurate details. A business account must be opened by someone allowed to act for that business.</li>
          <li>An account is either a creator or a brand, and that can't change.</li>
          <li>Keep your sign-in safe. You're responsible for what happens in your account; tell us straight away if you think someone else used it.</li>
        </ul>
      </section>

      <section>
        <h2>What DealMeet AI does, and doesn't</h2>
        <ul>
          <li>We help creators and brands find each other, agree terms and get paid. We aren't a party to the deals you make, and we don't promise any number of offers, deals or earnings.</li>
          <li>Prices, matches, plans and AI-written drafts are estimates and suggestions from the data available. Check them before you rely on them.</li>
          <li>Numbers from YouTube and Instagram are only as current as their last sync, and are labelled with their source.</li>
        </ul>
      </section>

      <section>
        <h2>Deals and payments</h2>
        <ul>
          <li>When a contract is signed, the brand pays the agreed amount into escrow through Razorpay. The creator is paid when the brand approves the post, or after the review window if the brand doesn't respond.</li>
          <li>Each side must do what the contract says: creators deliver the agreed posts with the required disclosures; brands review on time and pay.</li>
          <li>Until live payments are switched on for this site, payments are marked "simulated" and no money moves.</li>
          <li>Taxes on what you earn or pay are your responsibility. Invoices are made from deal details you can check.</li>
        </ul>
      </section>

      <section>
        <h2>Your content</h2>
        <p>You keep ownership of what you post and upload. You let us store and show it as needed to run DealMeet AI (for example your public page and media kit). A brand's right to use a creator's content is only what your contract says.</p>
      </section>

      <section>
        <h2>Rules</h2>
        <ul>
          <li>No fake numbers, fake accounts, impersonation or misleading claims.</li>
          <li>No harassment, spam or scams, and no content that breaks the law or the platforms' rules.</li>
          <li>Paid partnerships must be labelled as Indian advertising rules require.</li>
          <li>No scraping, automated bulk use, or attempts to get around security or limits.</li>
        </ul>
        <p>You can report anything that breaks these rules from the app. We may remove content or suspend accounts that break them, and we log every such action with its reason.</p>
      </section>

      <section>
        <h2>Ending your account</h2>
        <p>You can delete your account at any time from Help → Your account, once no deal has work or money in progress. We may suspend an account that breaks these terms; contact us if you think we got it wrong.</p>
      </section>

      <section>
        <h2>Liability</h2>
        <p>DealMeet AI is provided as it is. To the extent the law allows, we aren't liable for indirect losses or for what creators and brands do under their deals, and our total liability to you is limited to the fees you paid us in the 12 months before the claim. Nothing here limits rights you have under Indian consumer law.</p>
      </section>

      <section>
        <h2>Law and disputes</h2>
        <p>
          These terms are governed by the laws of India. Disputes go to the courts of {o?.city ? o.city : <Missing />}, after you've first tried to resolve them with us.
        </p>
      </section>

      <section>
        <h2>Contact</h2>
        <Contact o={o} />
      </section>
    </Page>
  );
}
