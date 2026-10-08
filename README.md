# JodiDar AI

> Other dashboards tell creators how they're doing. JodiDar AI tells them what to do next, prices it fairly, and makes sure they get paid.

A creator monetisation and brand opportunity engine, built by **Team TheVortex** for **CodeX 3.0** (Problem Statement 3).

## Run it

You need **Node 20+** and **Python 3.10+**. Nothing else: no keys, no database, no internet after the first install.

```bash
make dev        # or: npm run dev
```

The first run creates a Python virtual environment and installs dependencies. Then:

| What | Where |
| --- | --- |
| App | http://localhost:5173 |
| Side-by-side demo | http://localhost:5173/demo/compare |
| API health | http://localhost:8000/api/health |

Other commands:

```bash
make test       # engines, copy rules (no promises), no-scraping check, type check
make shots      # screenshots of every screen at 390 px and 1440 px + accessibility audit
make reset      # restore the seeded demo data while the app is running
```

## Offline by default

| Service | With keys | Without keys |
| --- | --- | --- |
| Database | MongoDB Atlas (`MONGODB_URI`) | In-memory (mongomock), seeded on start |
| AI | Live model (`ANTHROPIC_API_KEY` + `AI_MODEL`) | Deterministic templates |
| Payments | Razorpay **test mode** | Simulated escrow and UPI payouts |
| Auth | Firebase (Google) | Demo login role picker |

Copy `.env.example` to `.env` to enable any of them. Every one is optional.

## Data rules

- No scraping and no unauthorised platform access. Data comes only from official OAuth (mocked), what a creator types or uploads, and seeded mock data. `backend/tests/test_no_scraping.py` enforces this.
- No promises. Every forecast is a range with assumptions and a confidence level, labelled "Estimate, not a promise". `shared/copy-rules.json` bans words like "guaranteed" and "overnight"; the build fails if UI copy uses them.
- **Creator A** is a reference profile based on a real creator interview. Identity withheld; some fields simulated. Every field carries a `real` or `simulated` provenance flag, and the UI marks simulated values. All other profiles and brands are fictional.

## Project layout

```
backend/   FastAPI + Pydantic + scikit-learn + ReportLab (engines, seed data, API)
frontend/  React + TypeScript (Vite), Tailwind, Radix/shadcn-style components, Framer Motion, Recharts
shared/    Copy rules used by both test suites
qa/        Playwright screenshot and accessibility pass (localhost only)
scripts/   Cross-platform dev and test runners
```
