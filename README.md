# JodiDar AI

> Other dashboards tell creators how they're doing. JodiDar AI tells them what to do next, prices it fairly, and makes sure they get paid.

A creator monetisation and brand opportunity engine, built by **Team TheVortex** for **CodeX 3.0** (Problem Statement 3). It runs locally with one command and works fully offline on seeded mock data.

- **Creator Studio** (mobile-first, dark): your stage, your next 3 moves, a fair price for every brand reel, a growth roadmap, ranked money paths, opportunities you opt in to, and deals funded through escrow before you post. English or हिंदी.
- **Brand Console** (desktop, light): campaigns, creators ranked by audience fit with only the fields each creator chose to share, a collective builder for small creators, and the same deal rail from the brand's side.
- **Demo screens**: `/demo/compare` puts Creator A and Creator B side by side with a guided, captioned walkthrough; `/demo/live` runs a creator phone and a brand console next to each other, in sync.

## Run it

You need **Node 22.12+** (20.19+ also works) and **Python 3.10 to 3.14** (3.13 recommended). Nothing else: no keys, no database, and no internet after the first install.

On Windows, clone or unzip the project into a short folder such as `C:\JodiDar-AI`: the Python packages have long file paths, and Windows limits a path to 260 characters unless long paths are turned on.

```bash
make dev        # or: npm run dev   (works on Windows too)
```

The first run creates a Python virtual environment and installs dependencies (a few minutes). After that it starts in seconds.

| What | Where |
| --- | --- |
| App | http://localhost:5173 |
| Creator A vs Creator B, guided | http://localhost:5173/demo/compare?guide=1 |
| Live deal demo (phone + console) | http://localhost:5173/demo/live |
| API health | http://localhost:8000/api/health |

Other commands. Each `make` command has an `npm run` twin for Windows. Run `make setup` or `make dev` once first to install dependencies; `e2e`, `shots` and `reset` also need the app running.

```bash
make setup      # or: npm run setup   install dependencies only
make demo       # or: npm run demo    build the web app and serve everything from one port: http://localhost:8000
make test       # or: npm test        API tests, copy rules on UI strings, type check
make e2e        # or: npm run e2e     click through 17 key journeys in a real browser
make shots      # or: npm run shots   every screen at 390 px and 1440 px, plus an accessibility audit
                # (e2e and shots need a browser once: npx playwright install chromium)
make reset      # or: npm run reset   restore the seeded demo data (the app also has a "Reset demo" button)
```

## Environment variables

Every variable is optional. Copy `.env.example` to `.env` to turn a service on; with nothing set, each one falls back to a deterministic offline version and every screen still works.

| Variable | Used for | When it's not set |
| --- | --- | --- |
| `MONGODB_URI`, `MONGODB_DB` | MongoDB Atlas (or any MongoDB), with TLS certificates from certifi | Without `USE_MOCK_DB=1`, startup stops with a clear message. The API never falls back to memory on its own |
| `USE_MOCK_DB` | `1`: in-memory database (mongomock); data is lost on restart. `make dev` sets it when `MONGODB_URI` is empty; the Docker image sets it for the shared demo | `0` |
| `ANTHROPIC_API_KEY`, `AI_MODEL` | Live AI for caption tagging, topic ideas and media-kit copy, via the official SDK with structured output validated by Pydantic. Both must be set | Deterministic templates from the same numbers |
| `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET` | Razorpay **test mode** for the brand's payment into escrow (`rzp_test_` keys only). Each order is stored with its deal and amount; checkout must match both, and a payment is used once. A failed Razorpay call is an error (502), never a simulated success | Demo mode: a simulated payment, labelled so. Otherwise funding answers 503 and no money moves |
| `RAZORPAY_WEBHOOK_SECRET` | Verifies Razorpay webhooks at `/api/payments/razorpay/webhook` (`payment.captured`, `order.paid`, `payment.failed`). Each event is applied once | The webhook answers 503 |
| `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`, `VITE_FIREBASE_PROJECT_ID`, `VITE_FIREBASE_APP_ID` | Google and phone (OTP) sign-in in the browser, through Firebase | Email and password only; the page says Google and phone sign-in aren't configured |
| `FIREBASE_SERVICE_ACCOUNT_JSON` or `GOOGLE_APPLICATION_CREDENTIALS`, `FIREBASE_PROJECT_ID` | Server-side check of every Firebase ID token (Admin SDK): signature, expiry, this project, not revoked | `POST /api/auth/firebase` answers 503 |
| `YOUTUBE_API_KEY` | Real YouTube channel numbers: the public "What am I worth?" page (`/worth`) and linking a channel by @handle | Both say YouTube data isn't connected |
| `IG_APP_ID`, `IG_APP_SECRET`, `IG_REDIRECT_URI`, `FRONTEND_URL`, `TOKEN_ENC_KEY` | Connecting Instagram with its official login (read-only), real post checks on deals | Instagram shows "not available"; post checks read "not checked" |
| `IG_GRAPH_VERSION`, `IG_DEMOGRAPHICS_TIMEFRAME` | Meta Graph API version and the audience-demographics window | `v25.0`, `this_month` |
| `DEMO_MODE` | `1`: the sandbox. Seeded personas, persona sign-in, **Reset demo** and timed resets. `make dev`, `make demo` and the Docker image set it unless you set `DEMO_MODE=0` | `0`: real accounts only. No seeded data, no persona sign-in, no reset |
| `SESSION_HOURS` | How long a sign-in lasts | 72 |
| `DEMO_TODAY` | The date the demo treats as today, so seeded deadlines line up (default `2026-10-08`) | `2026-10-08` |
| `DEMO_RESET_MINUTES` | On a shared URL, put the demo data back to its seeded state every N minutes (skipped while someone changed something in the last 5 minutes). The Docker image sets 30 | Never resets on its own |
| `AI_MAX_CALLS_PER_HOUR` | Cap on live AI calls across all visitors; beyond it, templates are used | 100 |

Every AI call goes through one function with a fallback: if the key is missing, the call fails, the reply breaks the copy rules, or it quotes a number that isn't in our data, the template is used instead. Answers are cached.

## Database

`backend/app/db.py` is the only place that connects to MongoDB. It creates its indexes on every start (safe to repeat): unique `users.email`, `users.firebase_uid`, `creators.handle`, `brands.slug`, `connections (user_id, platform)` and `posts (creator_id, platform, post_id)`, plus `metric_snapshots (creator_id, platform, date)` and indexes on owner ids, deal stage and campaign status. `/api/health` pings it and reports `mock`, `atlas` or `mongodb` (503 when the ping fails).

Load the sample data, every record marked `source: "synthetic"`:

```bash
make seed                                     # or: npm run seed   (only into empty collections)
make seed ARGS="--reset --confirm-reset"      # or: npm run seed -- --reset --confirm-reset
```

On a real database `--reset` needs `--confirm-reset` and replaces only records marked synthetic and the seeded demo accounts; real accounts and their data stay. The **Reset demo** button and `DEMO_RESET_MINUTES` exist only in demo mode.

**Atlas setup** (one time):

1. Create a free cluster at cloud.mongodb.com.
2. Database Access: add a database user with a strong password (read and write to any database is enough).
3. Network Access: allow Render's outbound IP addresses (Render dashboard → your service → Connect → Outbound), or 0.0.0.0/0 for the hackathon only, with that strong password.
4. Connect → Drivers: copy the `mongodb+srv://...` string and put the password in it.
5. On Render (Environment) set `MONGODB_URI` to that string, `MONGODB_DB=jodidar` and `USE_MOCK_DB=0`. Locally, put the same in `.env`.
6. Optional: run `make seed` once against it to load the sample data.

`TEST_MONGODB_URI=... make test` also runs an integration test that writes, reconnects with a new client and reads back.

## Deploy

The repo builds into one container: the API serves the built web app on the port the host gives it (`$PORT`, default 8000).

```bash
docker build -t jodidar-ai .
docker run -p 8000:8000 jodidar-ai      # http://localhost:8000
```

- **Render**: New → Blueprint → pick this repository → Apply. `render.yaml` sets up a free Docker web service with the health check at `/api/health`. Free services sleep after 15 minutes without visitors; the first visit after that takes about a minute.
- **Any other Docker host** (Railway, Fly.io, Google Cloud Run, Hugging Face Spaces): point it at the `Dockerfile`. Health check path: `/api/health`.
- **Run one instance with one worker** while `USE_MOCK_DB=1`: the demo data lives in the server's memory, so a second instance would see different data. With Atlas (`MONGODB_URI`, `USE_MOCK_DB=0`) data survives restarts.
- **Everyone shares one demo.** The image runs with `DEMO_MODE=1`. Data resets on every restart, and every 30 minutes when idle (`DEMO_RESET_MINUTES`). The Studio and Console say so next to **Reset demo**, which resets it for everyone. Set `DEMO_MODE=0` on the host for real accounts only: then there is no seeded data, no persona sign-in and no reset.
- **Leave `ANTHROPIC_API_KEY` unset on a public URL**, or set a spend limit on the key: every visitor could otherwise trigger paid calls (capped by `AI_MAX_CALLS_PER_HOUR`).
- Razorpay accepts `rzp_test_` keys only. `VITE_FIREBASE_*` values are baked in at build time (Docker build args), and the deployed domain must be added to Firebase's authorised domains.
- Visitor-created records are capped (100 sign-ups, 50 new brands, 20 campaigns or collabs each, 30 bookings per creator, 50 offers per brand), and requests over 256 KB are refused.

## Architecture

```mermaid
flowchart LR
  subgraph WEB["Web app: React + TypeScript (Vite)"]
    CS["Creator Studio<br/>EN / हिंदी"]
    BC["Brand Console"]
    DEMO["/demo/compare and /demo/live<br/>phone and browser frames"]
    SYNC(["Live sync<br/>BroadcastChannel"])
  end

  subgraph API["API: FastAPI + Pydantic"]
    ROUTES["Routers<br/>creators, market, brands, deals, kit, demo"]
    subgraph ENG["Engines"]
      NS["Next-Step Engine<br/>learning loop"]
      FP["Fair-Price AI<br/>+ GBR cross-check"]
      TR["Trust Score<br/>IsolationForest"]
      COL["Collective Builder"]
      DI["Durable-Income Score"]
      MP["Money paths, roadmap,<br/>matching, spam, brand safety"]
    end
    subgraph SVC["Services"]
      CON["Consent ledger"]
      RAIL["Deal rail + escrow<br/>(honest payment states)"]
      PDF["Invoices and media kit<br/>ReportLab"]
      AI["AI layer<br/>validated, cached, fallback"]
    end
  end

  DB[("MongoDB Atlas<br/>or in-memory mongomock")]
  SEED["Seed data<br/>Creator A, Creator B,<br/>58 fictional creators, 25 listers"]
  LLM["Language model<br/>(optional)"]
  PAY["Razorpay test mode<br/>(optional)"]
  FB["Firebase Auth<br/>(optional)"]

  CS & BC & DEMO -->|"/api (JSON)"| ROUTES
  DEMO -.->|frames| CS & BC
  SYNC -.-|refetch on every write| CS & BC
  ROUTES --> ENG & SVC
  ENG & SVC --> DB
  SEED --> DB
  AI -.-> LLM
  RAIL -.-> PAY
  CS -.-> FB
```

**Request flow.** A screen asks the API for one view (for example `/api/creators/cr_a/home`). The router loads the creator, runs the engines (stage, fair price, opportunities, money paths, durable income, next moves), and returns numbers together with a `why` block for each one: reasons, inputs with `real`/`simulated` provenance, and assumptions. The web app renders the numbers and puts the `why` one tap away.

**Live sync.** Every successful write in the web app is announced on a `BroadcastChannel`; every other open window or demo frame refetches what it shows. That is how the creator phone and the brand console on `/demo/live` stay in step without a server push.

### The engines, in short

| Engine | How it works |
| --- | --- |
| **Fair-Price AI** | Base = median views of the last 6 reels × the niche's CPM (₹100–200 per 1,000 views). Then capped adjustments: engagement ±15%, audience fit −20%/+12%, consistency ±8%, brand safety down to −15%, trust −20%/+5%, usage and exclusivity up to +40%. Shown as a waterfall next to the follower-based price. A GradientBoostingRegressor trained on 4,000 synthetic deals cross-checks the result. |
| **Trust Score** | IsolationForest over growth spikes, views and likes per follower, comments per like, generic-comment share and follow ratio. A small shield with the top two reasons; low-trust profiles are ranked last and kept out of collectives. |
| **Next-Step Engine** | Candidate moves from money, growth and opportunity generators; the best of each, with a reason, a ₹ or reach range, an effort size and a "Why?". Marking a move done (worked / partly / didn't land) picks next week's follow-up: lock the rate, offer a bundle, make it a series, or test a new hook. |
| **Collective Builder** | Greedy knapsack on effective reach × fit per rupee, with an audience-overlap penalty (city × language × niche) and a trust threshold of 60. Creators who opted in are included first. One escrow payment for the pack, split by member. |
| **Durable-Income Score** | 100 × (0.5 diversification + 0.25 recurring share + 0.25 payment reliability), where diversification is 1 − HHI over income sources. Warns when one source is above 70%. |
| **Money paths** | Brand deals, services, digital products, affiliate, PR and collectives, each scored on fit, size against the creator's goal, and ease. Expertise-first creators (a skill, a small audience) see services first. |
| **Matching and consent** | Audience fit on niche, age, gender, language and region. Brands only see the fields a creator granted (stats, demographics, rate card); everything else is redacted and every profile a brand opens is logged in the consent ledger. |
| **Regional language** | Caption tagging by Unicode script and lexicons (Hindi, Hinglish, Tamil, Telugu, Kannada, Malayalam, Marathi, Bengali, Gujarati), topic ideas in the creator's language, and Hindi copy for the Studio. |

### Silent features

These stay out of the way until they matter:

- **Trust Score** badge with two reasons.
- **Low-offer alert** with a one-tap counter at the fair price.
- **Brand-safety notes**, with the fix already suggested to the creator.
- **Overlap de-dup** in collectives.
- **Spam and duplicate listings** hidden from creators.
- **Payment-delay nudges**, automatic approval after the review window, and auto-invoices.
- **Media kit PDF** and a `/c/:handle` link-in-bio page where brands can book the creator.
- **"Why?" popovers** on every number.
- **EN/हिंदी toggle**.

### Motion and 3D

Motion is there to explain, not decorate. Every effect checks reduced motion first and falls back to a still, fully readable layout.

| Where | What it does |
| --- | --- |
| Landing (1280 px and wider) | A 3D "creator core" with brand cards and rupee coins in orbit, following the pointer and the scroll |
| Creator Studio home | **Reach vs followers in 3D**: the last 6 reels rise as bars through a glass plane set at the follower count, so "reach is about 7x followers" is visible at a glance. Hover a bar for its views |
| Brand Console overview | **Deal flow in 3D**: the six rail stages as rings on a glowing track, a coin for each deal at its stage, and tokens flowing from offer to payout |
| Brand Console campaign | **Match space**: matched creators placed by fair price, reach and trust, coloured and sized by fit. Drag to turn it, hover for details, click to open a profile |
| Everywhere | Pages ease in; cards reveal and stagger as they scroll into view; move and KPI cards tilt toward the pointer; key numbers count up; a scroll-progress bar; the aurora background drifts with parallax |

The 3D scenes:

- Use three.js through React Three Fiber and drei.
- Load lazily: screens without 3D never download three.js.
- Pause when off screen.
- Fall back to 2D when WebGL isn't available.
- Use procedural lighting, so nothing is fetched from the network.
- Carry a text description for screen readers, and the same numbers are always in the HTML next to them.
- Leave the page scrolling normally: touch never rotates a scene.

### The deal rail

Offer → Contract (both sides e-sign) → Escrow funded → Post submitted → Approved → Paid out.

- A creator posts only once escrow is funded: a verified Razorpay test payment, or in demo mode a simulated one (labelled "simulated, no money moved").
- The brand reviews the post link and approves it or asks for a revision with a reason. If the brand doesn't respond within 3 days of the review deadline, the post is approved automatically.
- Automatic post checks need the creator's connected account. Until then each check reads "not checked" and the brand's review decides.
- **There is no payout integration.** A deal funded through Razorpay stops at "Approved, payout not connected". In demo mode a simulated payment gets a simulated payout, labelled so, with no bank reference. Nothing is called paid unless it was.
- Collectives fund once for the whole pack; each member's share is released after their post is approved.
- `/api/health` reports the real modes of payments, payouts, social data and post checks.

## 3-minute demo script

Before you start, click **Reset demo** (top of `/demo/compare`). On a shared URL, reset only when you start your own walkthrough: it resets the data for everyone. Present on a laptop or projector at 1440 px or wider.

| Time | Do this | Say this |
| --- | --- | --- |
| 0:00 | Open the app (http://localhost:5173 locally, or your deployed URL) and click **Watch the demo**. The guided demo starts on `/demo/compare`. | "Same engine, two very different creators. Every number has a reason, and every range is an estimate, not a promise." |
| 0:15 | Step 1 → 2 (press →). | "Creator A makes anime edits, 21.3K followers, and already earns. Creator B cooks Tamil home food with 2K followers. A is *Earning, underpriced*; B is *Starting*." |
| 0:40 | Step 3: Fair price. Open A's **Why?**. | "A's reels reach about 7x their followers. Priced on reach that's ₹17K–18K a reel; priced on followers it's ₹7K, which is what they quote. Every adjustment is capped and explained." |
| 1:05 | Steps 4–5: Roadmap and money paths. | "A keeps their best format and adds original voiceover, which removes a copyright risk. B fills a gap nobody else in Tamil food is covering: quick breakfasts. Money paths are ranked against each goal: anime-merch affiliate and gaming collectives for A; a food collective, a ₹199 e-book and kitchenware affiliate for B." |
| 1:30 | Steps 6–7. Then press **P** for two phones. | "Matches are opt-in: brands see only what each creator shares. And this is what each creator actually sees each week: their next 3 moves." On A's phone, tap **हिं** to show the Hindi Studio. |
| 1:55 | Click **Live deal demo**. On the phone tap **Counter at ₹17,362**, then **Send counter**. | "Senpai offered ₹7,300, 58% below fair. One tap counters at the fair price." |
| 2:15 | In the console: **Accept ₹17,362 and sign** (confirm in the dialog) → **Fund escrow** → **Pay ₹17,362 (simulated)**. On the phone: **Submit post link** (any `instagram.com/reel/...` link). In the console: **Approve post**. | "Both sides sign. The brand funds escrow before the creator posts, then reviews the post and approves it. In the demo the payment and payout are simulated and say so; with Razorpay connected the deal stops at 'payout not connected' until a payout partner is added. Each side updates live." |
| 2:35 | Open the Brand Console campaign (`/brand/campaigns/lst_senpai_hoodie?as=br_senpai`) and turn the **Match space**. | "Brands see every match by price, reach and trust. Up and to the left is more reach per rupee; hollow spheres are weak trust or unshared stats." |
| 2:45 | Back on **Live deal demo**, switch the scenario to **Collective**. On the phone, open the Thalam Foods collective, tap **Opt in**, then **Opt in and share**. The pack updates in the Thalam Foods console. | "Small creators get big-brand deals as a 20-creator collective, with overlap removed and low-trust profiles left out." |
| 2:55 | Close. | "No guarantees, no scraping, and the reference creator stays anonymous. That's JodiDar AI." |

Keyboard: **P** toggles phone view anywhere. In the guided demo, **←** and **→** move between steps and **Esc** ends it. Any link takes `?phone=1` to open in phone view and `?lang=hi` to open the Studio in Hindi.

## Real YouTube data and "What am I worth?"

`/worth` is public: type a YouTube @handle (or channel link) and see the channel's real numbers, labelled **Live data**, and an estimate for one brand Short and one brand integration in a long video.

- **Priced on views, never subscribers**: the median views of the channel's recent videos (from the last 30) × the niche's rate per 1,000 views, through the same Fair-Price engine. Shorts and long videos are priced separately because their views aren't comparable. Videos from the last 3 days aren't counted yet.
- With fewer than 3 settled videos of a format, it says there isn't enough data instead of pricing. Public data has no engagement, audience or trust signals, so there are no adjustments and the range is wider; it stays labelled **Estimate**.
- The API has no "is a Short" flag: up to 60 seconds counts as a Short, or up to 3 minutes when tagged #shorts.
- **Quota**: only 1-unit calls (`channels.list` by handle or id, `playlistItems.list`, `videos.list`); never `search.list` (100 units). Every response is cached in the database for 12 hours, and the public lookup is rate-limited per IP (20 an hour).
- Clear messages for an unknown handle, a used-up daily quota, a channel that hides its subscriber count, and YouTube being unreachable.
- In the Studio, **Connections** links the creator's own channel: the summary goes to `creators.channels.youtube` (`creators.platforms` was already the list of platforms a creator says they use), each video to `posts` and one `metric_snapshots` row per day, all with `source: "youtube_api"` and `fetched_at`. Unlinking deletes them. A channel linked by handle is public data, so it's marked "Ownership not verified" until YouTube Analytics is connected, and one channel can't be linked to two profiles.

**Google Cloud setup**: console.cloud.google.com → create a project → APIs & Services → Library → enable **YouTube Data API v3** → Credentials → Create credentials → API key. Restrict it to the YouTube Data API v3 and set `YOUTUBE_API_KEY`. The default quota is 10,000 units a day; one uncached lookup costs 3.

## Connecting Instagram

Creators connect Instagram from **Connections** with the Instagram API with Instagram Login (Business Login). Before the login opens they see: "We can see: your profile, posts, reach and audience age/gender/city. We can't: post, read your DMs or see your password. You can disconnect anytime."

- **Scopes**: `instagram_business_basic` and `instagram_business_manage_insights` only. No passwords, no posting, no scraping.
- **OAuth state**: random, HMAC-signed, valid for 10 minutes, single-use, and tied to the account that started it. A forged, expired, reused or someone else's state is refused.
- **Tokens**: the code is exchanged for a short-lived token and then a long-lived one (about 60 days), encrypted at rest with Fernet (`TOKEN_ENC_KEY`) in `connections`, with its expiry and granted scopes. Tokens are never logged and never reach the browser.
- **Sync** (on connect and **Sync now**, 6 an hour): `/me` (username, account type, followers, media count, picture), `/me/media` (latest 50 posts), per-reel insights for the latest 12 reels (views, reach, saves, shares), account `reach` and `views` over 28 days, and `follower_demographics` and `engaged_audience_demographics` by age, gender, city and country (`metric_type=total_value`, `timeframe` from `IG_DEMOGRAPHICS_TIMEFRAME`). Stored with `source: "instagram_api"` and `fetched_at` in `creators.channels.instagram`, `posts` and a daily `metric_snapshots` row.
- **The price runs on it**: connected reels replace the profile's sample reels, so the fair price uses real views, saves and shares, and its label changes from "Estimate from sample data" to "Estimate from Instagram data". It's still an estimate, never "verified".
- **Refresh**: an in-process daily job refreshes tokens older than 24 hours that expire within 10 days (`refresh_access_token`); each sync also refreshes first, for hosts that sleep. A Render Cron Job isn't needed.
- **Disconnect** deletes the token and every Instagram post, snapshot and audience number, and puts back the profile's previous numbers.
- Expired or revoked tokens ("Reconnect Instagram"), rate limits, personal accounts ("switch to a Creator or Business account") and accounts under 100 followers (no demographics) each get a clear message.
- **Deal post checks**: when a creator submits an Instagram link on a deal, it's checked against the connected account: the post is on that account, it was published after the contract was signed, and the caption mentions the brand. Results are stored with when they were checked. The paid-partnership label isn't in the API, so it reads "not checked". The brand still approves before payment.

**Meta dashboard steps** (one time):

1. developers.facebook.com → My Apps → Create app → use case **Other** → type **Business**.
2. Add the **Instagram** product → **API setup with Instagram login**.
3. Under **Business login settings**, add the OAuth redirect URI exactly as in `IG_REDIRECT_URI` (HTTPS: your Render URL plus `/api/connect/instagram/callback`, or an ngrok URL when running locally).
4. Copy the **Instagram app ID** and **Instagram app secret** into `IG_APP_ID` and `IG_APP_SECRET` (secrets on Render, never committed).
5. Permissions: `instagram_business_basic` and `instagram_business_manage_insights`.
6. While the app is in **development mode**, only Instagram accounts added as **Instagram Testers** can connect (App roles → Roles → Instagram Testers; each tester accepts the invite in Instagram → Settings → Website permissions → Apps and websites → Tester invites). Each tester's account must be a **Creator or Business** account.
7. Generate `TOKEN_ENC_KEY` once (command in `.env.example`) and set it on the server.
8. Check the current Graph API version and the valid demographics `timeframe` values in Meta's changelog and the Instagram User Insights reference, and set `IG_GRAPH_VERSION` and `IG_DEMOGRAPHICS_TIMEFRAME` if they differ. The defaults (`v25.0`, `this_month`) were checked against secondary sources; Meta's own docs couldn't be opened from the environment this was built in.

## Accounts and permissions

Every private API route checks the signed-in account on the server, and that the account owns the creator profile, brand, campaign, deal, collective or invoice it touches. Nothing trusts a role or an owner id sent from the browser: a deal action's side (creator or brand) comes from the session.

- **Accounts** are creators or brands, chosen at sign-up and fixed after that. Admin is granted only from the server: `python -m app.admin_cli grant <email>` (run in `backend/`).
- **Sign-in**: Google or phone OTP through Firebase, or email and password (hashed with scrypt). Both stay: email and password works with no Firebase project. Five wrong passwords in 15 minutes pause sign-in for that email.
- **Firebase is verified on the server.** The browser sends the Firebase ID token once to `POST /api/auth/firebase`; the Admin SDK rejects forged, expired, revoked and other-project tokens, then the account is found or created by `firebase_uid` (unique) and the app starts its own session. A uid is never accepted without a verified token. The side (creator or brand) is picked at the first sign-in and can't change later; a verified Google email that matches an email-and-password account links to it.
- **Sessions**: a random token in an HttpOnly, SameSite=Lax cookie (Secure over HTTPS), or a `Authorization: Bearer` header for API clients. Only the token's SHA-256 hash is stored. Sessions last 72 hours (`SESSION_HOURS`) and signing out revokes them.
- **CSRF**: a write sent with only the cookie must carry an `X-Requested-With` header, which a cross-site form can't add. The web app always sends it.
- **Audit log**: sign-ups, sign-ins, sign-outs and every write (who, route, result) go to an append-only `audit` collection. Request bodies, passwords and tokens are never stored there.
- **401 and 403**: the app sends you to sign in when a session ends, and says plainly when a page belongs to another account or the other side.

### Firebase setup (one time)

1. Firebase console → create a project → Build → Authentication → Sign-in method: enable **Google** and **Phone**.
2. Authentication → Settings → Authorized domains: add `localhost` and your deployed domain (for example `jodidar-ai.onrender.com`).
3. Project settings → General → Your apps → add a Web app; copy its config into the `VITE_FIREBASE_*` variables. On Render, pass them as Docker build args (they're baked into the web build).
4. Project settings → Service accounts → Generate new private key. Put the JSON on one line in `FIREBASE_SERVICE_ACCOUNT_JSON` (a secret on Render), or point `GOOGLE_APPLICATION_CREDENTIALS` at the file locally. Never commit it.
5. Phone sign-in in development: add test phone numbers with fixed codes (Authentication → Sign-in method → Phone), so no real SMS is sent.

The web app and API are served from one origin (one Docker image), so the session cookie is first-party. If you ever host the web app on another domain (for example Vercel plus Render), the cookie becomes cross-site: use a shared parent domain, or `SameSite=None; Secure` cookies plus CORS for that one origin.

## Demo profiles

Demo mode only (`DEMO_MODE=1`, which `make dev` and the Docker image set). Sign in at `/login` with your own account, or pick a profile. Persona sessions are demo tokens kept per side, so a creator phone and a brand console can run side by side, and `?as=<profile id>` signs one tab or frame in as that demo profile. A demo reset removes accounts made during the demo; outside demo mode none of this exists.

| Profile | Who | What to look at |
| --- | --- | --- |
| **Creator A** | Anime-edit reels in Hindi and English, 21.3K followers. Reference profile based on a real creator interview: identity withheld, some fields simulated, and every simulated value is marked. | Fair price ₹17K–18K vs ₹7K on followers; low-offer alert; deal rail; media kit |
| **Creator B** | Tamil home cooking, 2K followers, ₹10K/month goal (fictional) | Tamil quick-breakfast gap; Thalam Foods collective; ₹199 e-book |
| **New creator** | Onboarding from scratch | Niche, platforms, format, audience stage, income goal, languages, city; mocked official login; caption reading |
| **Senpai Supply Co.** | Anime merch store (fictional) | Matches with trust and safety notes; offers; deals |
| **Thalam Foods** | Regional masala brand (fictional) | 20-creator South collective |
| **New brand** | Brand onboarding | Campaign set-up |

## Data rules

- **No scraping**, and no unauthorised platform access. Data comes only from official login (mocked here), what a creator types or uploads, and seeded mock data. `backend/tests/test_no_scraping.py` enforces this, and the QA scripts only ever visit localhost.
- **No promises.** Every forecast is a range with assumptions and a confidence level, labelled "Estimate, not a promise". `shared/copy-rules.json` bans words like "guaranteed", "viral", "overnight" and "100%", in English and Hindi. A check fails if they appear in:
  - UI copy (`frontend/scripts/check-copy.mjs`, run by `make test` and before every build);
  - backend source strings and API responses for a sample of creators and brands (`backend/tests/test_copy_rules.py`, run by `make test`);
  - rendered screens (`qa/screenshots.mjs`, run by `make shots`).
- **The reference creator stays anonymous.** Creator A has no name, photo, handle or city. Real values (followers, following, posts, the last 6 reels' views and dates, average likes and comments, best deal) carry a `real` provenance flag; the rest are `simulated` and marked in the UI. Every other profile, brand and listing is fictional, and no real brand logos are used.

## Accessibility

- Checked with axe-core (WCAG 2 A/AA plus best practices) on every screen at 390 px and 1440 px.
- Skip links in the Studio, the Console and the demo screens; visible focus rings; and keyboard support for all dialogs, popovers, segmented controls and the guided demo.
- Charts have text equivalents.
- Respects reduced motion: Framer Motion and CSS transitions are switched off.
- Hindi text uses Noto Sans Devanagari with letter-spacing turned off, so the headline bar stays intact.

## Tests and QA

| Command | What it checks |
| --- | --- |
| `make test` | 201 API tests (below), the copy rules on about 3,200 UI strings, and the TypeScript type check |
| `make e2e` | 17 journeys in a real browser (below) |
| `make shots` | 62 screenshots (31 screens × 390 px and 1440 px). Each screen is also checked with axe-core, against the copy rules, for console errors and for horizontal scrolling. Output in `qa/shots` and `qa/report/qa.json` |

The API tests cover:

- Honest payments: a failed provider call, a mismatched order or amount, a replayed payment, a webhook with a bad signature and a duplicate webhook; a funded deal that stops at "payout not connected"; revision requests.
- Instagram (against a fake Graph API): the OAuth state (forged, expired, reused, another account's), encrypted tokens that never reach the browser, the sync and the price label, no demographics under 100 followers, personal accounts, expired tokens, rate limits, token refresh, disconnect deleting everything, and deal post checks.
- YouTube data (against a fake Data API): median-views pricing per format, no `search.list`, the 12-hour cache, the per-IP limit, unknown handle, used-up quota, network failure, hidden subscribers, too few videos, linking with posts and a daily snapshot, unlinking, and owner-only access.
- Firebase sign-in: a forged token, an expired or revoked token, a token from another Firebase project (checked by the real Admin SDK, offline), a first sign-in, a role that can't change, and linking a verified email.
- Accounts and permissions: every private route answers 401 without a session, another account's records answer 403, expired, revoked and suspended sessions are refused, cookie writes need the app header, and admin can only be granted from the server.
- Creator A's and Creator B's expected outputs.
- Every engine.
- Consent redaction.
- The deal rail, escrow and auto-release.
- AI fallbacks.
- Hindi copy.
- Copy rules on source strings and live responses.
- The no-scraping check.
- Serving the built web app from the API: content types, and requests that try to reach files outside the build.
- Windows portability: date formatting and `.env` files saved by Windows tools.
- Consent and honesty on every screen: no audience numbers without consent, simulated data labelled, alerts that match what the app does.
- A public, shared demo: request and record limits, the booking reply, and the shared-demo flag.

The e2e journeys:

- The public "What am I worth?" page saying plainly when YouTube data isn't connected.
- The sign-in gate, and an email sign-up that sets up a brand, survives a reload and signs out.
- Onboarding.
- The weekly learning loop.
- Pricing per brand.
- "Why?" popovers.
- Collective opt-in.
- A brand sending an offer.
- Revoking consent.
- The full deal rail.
- Link-in-bio booking.
- Hindi.
- The guided compare.
- Phone view.
- Live sync.
- The 3D scenes drawing with WebGL.

## Project layout

```
backend/
  app/engines/     fair price, trust, next step, collective, durable income, matching, money paths, roadmap, spam, brand safety, Hindi copy
  app/services/    consent ledger, deal rail, payments, PDFs, view builders
  app/ai/          AI layer (validated output, copy rules, number grounding, cache, fallback) and regional caption tagging
  app/routers/     HTTP API
  app/seed/        Creator A (reference), Creator B, fictional roster, brands, listings, deals
  tests/           pytest suite
frontend/
  src/features/    creator (Studio), brand (Console), deals (shared deal view), demo (compare, live), public (landing, login, link-in-bio)
  src/components/  ui primitives, shared pieces (Why?, Trust, estimates, kit), charts, demo frames, motion, three (3D scenes)
  src/i18n/        English and Hindi
shared/            copy rules used by both test suites
qa/                Playwright screenshots, accessibility audit and e2e journeys (localhost only)
scripts/           cross-platform dev, demo and test runners
```

## Stack

- **Web**: React 19, TypeScript, Vite, Tailwind CSS 4, Radix primitives (shadcn-style), Framer Motion, three.js with React Three Fiber and drei, Recharts, Lucide, React Router, TanStack Query; Sora and Inter.
- **API**: FastAPI, Pydantic, scikit-learn, ReportLab, httpx.
- **Data and services**: MongoDB or mongomock; optional Firebase Auth, Razorpay test mode and a language model.
