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
make e2e        # or: npm run e2e     click through 16 key journeys in a real browser
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
| `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`, `VITE_FIREBASE_PROJECT_ID`, `VITE_FIREBASE_APP_ID` | Google sign-in before choosing a demo profile | Demo login with a profile picker |
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

## Accounts and permissions

Every private API route checks the signed-in account on the server, and that the account owns the creator profile, brand, campaign, deal, collective or invoice it touches. Nothing trusts a role or an owner id sent from the browser: a deal action's side (creator or brand) comes from the session.

- **Accounts** are creators or brands, chosen at sign-up and fixed after that. Admin is granted only from the server: `python -m app.admin_cli grant <email>` (run in `backend/`).
- **Sign-in**: email and password (hashed with scrypt). Five wrong passwords in 15 minutes pause sign-in for that email.
- **Sessions**: a random token in an HttpOnly, SameSite=Lax cookie (Secure over HTTPS), or a `Authorization: Bearer` header for API clients. Only the token's SHA-256 hash is stored. Sessions last 72 hours (`SESSION_HOURS`) and signing out revokes them.
- **CSRF**: a write sent with only the cookie must carry an `X-Requested-With` header, which a cross-site form can't add. The web app always sends it.
- **Audit log**: sign-ups, sign-ins, sign-outs and every write (who, route, result) go to an append-only `audit` collection. Request bodies, passwords and tokens are never stored there.
- **401 and 403**: the app sends you to sign in when a session ends, and says plainly when a page belongs to another account or the other side.

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
| `make test` | 168 API tests (below), the copy rules on about 3,200 UI strings, and the TypeScript type check |
| `make e2e` | 16 journeys in a real browser (below) |
| `make shots` | 62 screenshots (31 screens × 390 px and 1440 px). Each screen is also checked with axe-core, against the copy rules, for console errors and for horizontal scrolling. Output in `qa/shots` and `qa/report/qa.json` |

The API tests cover:

- Honest payments: a failed provider call, a mismatched order or amount, a replayed payment, a webhook with a bad signature and a duplicate webhook; a funded deal that stops at "payout not connected"; revision requests.
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
