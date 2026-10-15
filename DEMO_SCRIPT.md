# DealMeet AI: demo script

Exact click paths for the four walkthroughs judges ask about. Every path here is also checked by a browser test (named in each section), so the labels match the app.

**Before you start**

- Local: `make dev`, then open http://localhost:5173. Deployed: your URL (for example `https://dealmeet-ai.onrender.com`).
- Click **Reset demo** first (in the Studio or Console menu). On a shared URL it resets the data for everyone, so do it only when your walkthrough starts.
- `?as=<profile id>` signs a tab in as a demo profile: `cr_a` (Creator A), `cr_b` (Creator B), `br_senpai` (Senpai Supply Co.), `br_thalam` (Thalam Foods). Use two browser windows, one per side.
- Say it plainly: prices are **estimates**, the demo's numbers are **Sample data** unless a badge says **Live data**, and demo payments are **simulated**.

For the 3-minute pitch with timings, see [the README's demo script](README.md#3-minute-demo-script).

---

## 1. Live data (linking a channel)

Needs `YOUTUBE_API_KEY` on the server ([setup](README.md#real-youtube-data)). Without it, Connections says YouTube data isn't connected, which is also worth showing: no made-up numbers.

1. Signed in as a creator (`/creator/connections?as=cr_b`), click **Connect** on YouTube, type the channel's handle and click **Connect channel**.
2. Point at the **Live data** badge and the fetched date: the numbers come from the YouTube Data API, cached for 12 hours.
3. On **Money**, the YouTube formats in your rates now say "Estimate from YouTube data": priced on **median views** of recent videos, never subscribers. The channel is marked "Ownership not verified" until YouTube Analytics is connected.

There's no public lookup of other people's channels; visitors search creators who keep a public page instead (browser test: *Creators: a visitor picks a niche from the landing bar…*).

## 2. Connecting Instagram

Needs a Meta app, an HTTPS redirect URI and the creator added as an Instagram Tester ([setup](README.md#connecting-instagram)). Without them, the Instagram card says it isn't available on this server.

1. Sign in as a creator whose Instagram account is a **Creator or Business** account and an **Instagram Tester** on your Meta app (a real account, not a demo profile: use **Create an account** on `/login`).
2. Open **Connections** (`/creator/connections`).
3. Click **Connect Instagram**. Read the consent aloud: what DealMeet can see, what it can't (post, read DMs, see your password), and that you can disconnect anytime.
4. Click **Continue to Instagram**, sign in on Instagram's own page and approve the two read-only permissions.
5. Back on **Connections**: followers, the latest posts, reel insights and (from 100 followers) audience age, gender and city, each labelled **Live data** with when it was fetched.
6. Open **Money**: the fair price now runs on the real reels and says "Estimate from Instagram data".
7. Click **Sync now** to refresh; **Disconnect** → **Disconnect and delete** removes the token and every Instagram number.

## 3. Brand search → Dream Brand → pitch → the brand accepts

Browser tests: *Brands: search the directory, save a Dream Brand…* and *Pitch: a creator writes a pitch…*.

Window 1, creator:

1. Open **`/brands?as=cr_a`**. In **Search**, type `senpai`.
2. Click **Senpai Supply Co.** Point at "N creators with connected accounts want to work with this brand".
3. Click **Save as Dream Brand**. Open **`/creator/brands?as=cr_a`**: Senpai Supply Co. is listed, and you'll be told when it opens a campaign.
4. Now as Creator B: open **`/brands/thalam-foods?as=cr_b`** and click **Pitch this brand**.
5. Click **Write my pitch to Thalam Foods**. Point at **Numbers it can use**: the pitch uses only Creator B's own numbers, each with its source, and the price range comes from the fair-price engine, never the AI.
6. Click **Send**, then **Confirm**. "Sent to Thalam Foods" (5 pitches a week).

Window 2, brand:

7. Open **`/brand/inbox?as=br_thalam`** (**Fan Inbox**). Creator B's pitch is there, with fit and Fan Proof.
8. Click **Accept**, check the amount, click **Send offer**. It becomes an ordinary offer in **Deals**: the creator accepts or counters, both sign, the brand funds escrow before the post.

Back in window 1, **`/creator/deals?as=cr_b`** shows the offer from Thalam Foods.

## 4. The public creator page

Browser tests: *Public page: write a positioning…* and *Link-in-bio: a brand books from the public page…*.

1. Open **`/creator/kit?as=cr_a`** (**Media kit**).
2. Click **Write my positioning**, edit the **Positioning** line if you like, click **Save**.
3. Turn on **Show the positioning on my public page**. Under the sharing settings, choose what's public (stats, audience, rates).
4. Open **`/c/creator.a`** in a private window (no sign-in): the positioning, badges that appear only with data behind them, an **Estimated range**, and a **QR code** with **Download QR**.
5. Click **Book Creator A**, fill **Brand** (`Otaku Threads`) and **Work email** (`hello@otaku.test`), click **Send booking request**.
6. Back in the Studio, **`/creator/deals?as=cr_a`** shows the request from Otaku Threads.

Optional: on the public page, **Report this profile** shows that any signed-in account can report a profile to the admins (5 a day).

---

## Extra: admin console (local demo only)

`make dev` turns on a **Demo admin** persona (`DEMO_ADMIN=1`; never on a shared URL). Browser test: *Admin: a deal party reports a problem…*.

1. As Senpai, open **`/brand/deals/dl_a_senpai?as=br_senpai`**, click **Report a problem with this deal**, pick **Harassment**, **Send report**.
2. Open **`/login`**, click **Demo admin**. The **Overview** shows 1 open report.
3. **Reports** → **Resolve**: the button stays disabled until you write a reason. Write one, **Resolve**.
4. **Accounts** → search `us_cr_b` → **Suspend** with a reason: Creator B is signed out and can't sign in. **Restore** with a reason.
5. **Audit log** → **Action starts with** `admin_`: both actions with their reasons. Secret-looking fields are always hidden.

## Extra: real accounts, demo mode off

`make accounts` signs up a creator and a brand with email and password (demo mode off), onboards both, publishes a campaign, applies, sends an offer and signs it, reloading after every write, at 390 px and 1280 px. To click it yourself: run the API with `DEMO_MODE=0` and use **Create an account** on `/login`.
