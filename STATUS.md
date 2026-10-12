# Status

What's built, how it was checked, and what still needs credentials or infrastructure. Nothing here is production-ready; it's a hackathon build with honest edges.

**Statuses**

- **Tested**: implemented and tested (API tests, and browser tests where named).
- **Unverified**: implemented, tested against fakes or test doubles, but not yet run against the real external service.
- **Blocked**: needs credentials or infrastructure this environment doesn't have.
- **Not implemented**: not built; the app says so where it matters.

**Evidence at the time of writing** (all on the in-memory database, no external services):

| Check | Command | Result |
| --- | --- | --- |
| API tests | `make test` | 425 passed, 1 skipped (`test_db.py` real-MongoDB round trip, needs `TEST_MONGODB_URI`) |
| Copy rules on UI strings | `make test` | 5,922 strings, no promises |
| Type check | `make test` | clean |
| Demo journeys in a browser | `make e2e` | 30 of 30 pass |
| Real accounts, demo mode off, 390 px and 1280 px | `make accounts` | 16 of 16 pass |
| Screens at 390 px and 1440 px with axe-core, copy rules, console errors, sideways scroll | `make shots` | 98 screenshots, 0 need attention |
| CI | `.github/workflows/test.yml` | runs `make test`, then `make e2e` and `make accounts`, on every push; passing on GitHub |

---

## 1. Accounts, sessions and server-side permissions

| Part | Status | Evidence |
| --- | --- | --- |
| Email and password sign-up and sign-in (scrypt), throttled after 5 wrong passwords | Tested | `test_auth.py`; `make accounts` |
| Sessions: HttpOnly cookie or Bearer, hashed at rest, 72-hour expiry, revoke on sign-out | Tested | `test_auth.py`, `test_acceptance.py` (expired session per area) |
| Every private route needs a session; another account's records are 403; owner ids never from the browser | Tested | `test_auth.py` (all routes enumerated), `test_acceptance.py` |
| CSRF header on cookie writes | Tested | `test_auth.py` |
| Append-only audit log without secrets | Tested | `test_auth.py`, `test_admin.py` |
| Admin granted only on the server (`app.admin_cli`) | Tested | `test_auth.py`, `test_admin.py` |

## 2. Firebase sign-in, verified on the server

| Part | Status | Evidence |
| --- | --- | --- |
| ID token verified with the Admin SDK (forged, expired, revoked, other project refused) | Tested | `test_firebase.py` (real Admin SDK, offline keys) |
| Google and phone sign-in in the browser | Unverified | Needs a Firebase project (`VITE_FIREBASE_*`, service account); not run against one |
| Role fixed at first sign-in; verified email links to an existing account | Tested | `test_firebase.py` |

## 3. Honest payments, payouts and post checks

| Part | Status | Evidence |
| --- | --- | --- |
| Simulated payments in demo mode, labelled; refused outside demo without keys | Tested | `test_payments.py`, `test_screen_truth.py`; deal-rail journey |
| Razorpay test-mode orders, signature checks, one-use payments, webhooks applied once | Unverified | `test_payments.py` against a fake Razorpay; not run with real test keys |
| Payouts to creators | Not implemented | No payout partner (for example RazorpayX); a funded deal says "payout not connected" |
| Post checks on deals (on the connected account, after signing, caption mentions the brand) | Unverified | `test_instagram.py` against a fake Graph API |
| Paid-partnership label check | Not implemented | Not in Instagram's API; shown as "not checked" |

## 4. MongoDB Atlas instead of mongomock

| Part | Status | Evidence |
| --- | --- | --- |
| No silent fallback: unreachable `MONGODB_URI` stops startup with a clear message | Tested | `test_db.py` |
| Indexes created on start; `/api/health` reports mock, atlas or mongodb | Tested | `test_db.py` |
| Real Atlas round trip (write, reconnect, read) | Unverified | `test_db.py` integration test is skipped without `TEST_MONGODB_URI` |
| Seed script that replaces only synthetic records | Tested | `test_seed.py` |

## 5. Real YouTube data and "What am I worth?"

| Part | Status | Evidence |
| --- | --- | --- |
| Median-views pricing per format, 1-unit calls only, 12-hour cache, per-IP limit, clear failures | Tested | `test_youtube.py` against a fake Data API |
| Live lookups with a real key | Unverified | Needs `YOUTUBE_API_KEY`; the "not connected" path is a browser journey |
| Linking a channel by handle, posts and daily snapshots with `source: youtube_api` | Tested | `test_youtube.py` |

## 6. Connect Instagram and real post checks

| Part | Status | Evidence |
| --- | --- | --- |
| OAuth state (signed, 10 minutes, single use, tied to the account), encrypted tokens, sync, disconnect deleting everything | Tested | `test_instagram.py` against a fake Graph API |
| Real connection with a Meta app | Blocked | Needs a Meta app, an HTTPS redirect URI and Instagram Testers |
| Graph API version and demographics timeframe | Unverified | Defaults `v25.0`, `this_month` from secondary sources; settings `IG_GRAPH_VERSION`, `IG_DEMOGRAPHICS_TIMEFRAME` |

## 7. YouTube Analytics (optional)

| Part | Status | Evidence |
| --- | --- | --- |
| Token used once and never stored; channel must match the linked one; disconnect deletes snapshots | Tested | `test_youtube_analytics.py` against a fake API |
| Real Google OAuth with test users | Blocked | Needs the Analytics API enabled and test users on the OAuth consent screen |

## 8. Creator profile, completeness and brand-readiness

| Part | Status | Evidence |
| --- | --- | --- |
| Profile edits, validation, completeness, readiness with and without a connected account, self-reported numbers with history | Tested | `test_profile.py`; profile journey; `make accounts` |

## 9. AI growth coach

| Part | Status | Evidence |
| --- | --- | --- |
| Answers from the creator's own numbers with sources, measurable goals, caching and limits, model answers checked | Tested | `test_coach.py`, `test_ai_fallback.py`; coach journey |
| Live model answers | Unverified | Needs `ANTHROPIC_API_KEY` and `AI_MODEL`; templates otherwise |
| Hindi answers | Unverified | Only through the live-model path; templates are English |

## 10. Saved rates and media kit

| Part | Status | Evidence |
| --- | --- | --- |
| Saved rates next to estimates, Hindi kit and PDF with an embedded Devanagari font, immutable versions | Tested | `test_rates_kit.py`; rates and media kit journey |

## 11. Campaign lifecycle for brands

| Part | Status | Evidence |
| --- | --- | --- |
| Brand profile; drafts, validation before publishing, pause, resume, close; applications by state | Tested | `test_campaigns.py`; campaign journey; `make accounts` |

## 12. Shortlist, compare and draft offers

| Part | Status | Evidence |
| --- | --- | --- |
| Documented ranking weights and evidence, neutral scores for missing data, shortlists, compare, drafts sent only on confirm | Tested | `test_shortlist.py`; shortlist journey |

## 13. Brand directory, search and Dream Brands

| Part | Status | Evidence |
| --- | --- | --- |
| Search with escaped input and a fallback, unclaimed pages, claims, removal requests, Dream Brands | Tested | `test_directory.py`; directory journey |
| Atlas Search index | Unverified | `backend/atlas/brands_search.json`; needs an Atlas cluster |

## 14. Fan Proof, AI Pitch Builder and Brand Fan Inbox

| Part | Status | Evidence |
| --- | --- | --- |
| Fan Proof matching from API posts only, pitch drafts from the creator's facts, weekly limit, share links, inbox accept and decline | Tested | `test_pitches.py`; pitch journey |

## 15. Public creator page and branding

| Part | Status | Evidence |
| --- | --- | --- |
| Data-backed badges, case studies, positioning, QR code, escaped link previews, no private fields | Tested | `test_creator_page.py`, `test_static_serving.py`; public page and booking journeys |
| On-time badge | Tested | Shown as "On time: X of Y posts" rather than a percentage, to keep within the copy rules |

## 16. Contract versions, counter-proposals and deliverable reviews

| Part | Status | Evidence |
| --- | --- | --- |
| Versions with SHA-256 hashes, agreement on the same version, checked status machine, multi-link submissions, request keys | Tested | `test_contracts.py`, `test_deals.py`; contract journey; `make accounts` |
| A brand's offer counts as accepting version 1 | Tested | Design choice, documented in the README |

## 17. Creator collectives

| Part | Status | Evidence |
| --- | --- | --- |
| Explained picks, adjustable fees and deliverables, per-member confirmations, replacement, funding only when all confirm | Tested | `test_collectives.py`; collective journey |

## 18. Assistant actions with confirmation

| Part | Status | Evidence |
| --- | --- | --- |
| Tools run as the signed-in user with checked arguments; sending, publishing and money wait for Confirm (10 minutes, run once); audited | Tested | `test_assistant_tools.py`; assistant journey |
| Tool choice by the model | Unverified | Needs a model key; simple rules choose otherwise |

## 19. Administrator console

| Part | Status | Evidence |
| --- | --- | --- |
| Server-only admin role, `/admin` overview, actions each needing a reason, audit log viewer with redaction | Tested | `test_admin.py`; admin journey; 6 admin screens in `make shots` |
| User reports (deals only by their sides, 5 a day, duplicates) | Tested | `test_admin.py`, `test_acceptance.py` |
| Demo admin persona | Tested | Local demos only (`DEMO_ADMIN=1`), never on a self-resetting shared demo; `test_admin.py` |

## 20. TEE status and safe fallback

| Part | Status | Evidence |
| --- | --- | --- |
| Status `not_configured`, `available` or `failed` in `/api/health`, the brand's creator view, Privacy and the admin console | Tested | `test_tee.py`; TEE journey |
| Documented fallback: minimised data processed on our server, labelled | Tested | `test_tee.py` |
| AWS Nitro attestation verification (chain, signature, PCR policy, nonce, freshness, result binding) | Unverified | `test_tee.py` with a generated certificate chain and a verifier test double; never run against a real enclave |
| A real enclave and the enclave app | Blocked | Needs an EC2 instance with Nitro Enclaves and an enclave image; not in this repository |
| Demographics stored encrypted to the enclave | Not implemented | Depends on a TEE; documented as the next step |

## 21. Testing, setup docs and demo script

| Part | Status | Evidence |
| --- | --- | --- |
| Backend tests per area: happy path, invalid input, 401, 403, expired session, failed external call, duplicates | Tested | Area suites plus `test_acceptance.py` |
| Pure-function tests on the in-memory database: median-views pricing, Fan Proof matching, pitch rate limit | Tested | `test_pure.py`, and `test_pitches.py` for Fan Proof matching |
| Browser journeys with demo mode off at 390 px and 1280 px, reloading after writes | Tested | `qa/accounts.mjs` (`make accounts`) |
| GitHub Actions on every push and pull request | Tested | `.github/workflows/test.yml`; first runs on GitHub passed all three stages (`make test`, 30 demo journeys, 16 real-account steps): [push run](https://github.com/KeshavMishra0139/DealMeet-AI/actions/runs/38201960078), [pull request run](https://github.com/KeshavMishra0139/DealMeet-AI/actions/runs/38201961092) |
| README setup section, every env var, seed, switching mock and real data | Done | README: "Setup: from the demo to real services", "Environment variables" |
| `DEMO_SCRIPT.md` | Done | Click paths match the browser journeys named in it |

## Bugs found by the new tests and fixed

- A new marketplace with no listings crashed the creator's Home and Opportunities (the duplicate-listing check had nothing to compare). Found by `make accounts`; regression test in `test_acceptance.py`.
- The Money page crashed when no brand was verified yet, the normal state of a fresh deployment. Regression test in `test_acceptance.py`.
- Finishing brand onboarding bounced to the overview instead of the new-campaign form. Found by `make accounts`.
- Long creator handles or match reasons pushed a match row's columns into each other. Found by `make accounts`.

## Known deviations

- Connected-platform data lives in `creators.channels` (`creators.platforms` was already the list of platforms a creator says they use).
- Records carry `source` (`synthetic`, `youtube_api`, `instagram_api`, `manual`) and `fetched_at`; the reference creator also keeps its per-field `real`/`simulated` provenance so its few real values stay marked.
- Email and password sign-in stays alongside Firebase, so the app works without a Firebase project.
- `make dev` and the Docker image default to demo mode; the API itself defaults to demo mode off.
