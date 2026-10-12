#!/usr/bin/env node
// Real-account journeys with demo mode OFF, at 390 px and 1280 px: email sign-up,
// onboarding, profile edits, a campaign from draft to live, an application and an offer
// the creator signs. After each write the page is reloaded to check it was saved.
//
// Starts its own API on :8010 (DEMO_MODE=0, in-memory database) serving a fresh build of
// the web app, unless QA_ACCOUNTS_BASE points at a server that's already running:
//   node qa/accounts.mjs
//   QA_ACCOUNTS_BASE=http://localhost:8000 node qa/accounts.mjs   # must have DEMO_MODE=0
import { spawn, spawnSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..");
const isWin = process.platform === "win32";
const PORT = 8010;
const BASE = process.env.QA_ACCOUNTS_BASE ?? `http://localhost:${PORT}`;
if (!/^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(BASE)) throw new Error("QA only runs against localhost");

let server = null;
async function startServer() {
  console.log("Building the web app...");
  const b = spawnSync("npm", ["run", "build"], { cwd: join(root, "frontend"), stdio: "inherit", shell: isWin });
  if (b.status !== 0) throw new Error("web build failed");
  const python = isWin ? join(root, "backend", ".venv", "Scripts", "python.exe") : join(root, "backend", ".venv", "bin", "python");
  server = spawn(python, ["-m", "uvicorn", "app.main:app", "--port", String(PORT)], {
    cwd: join(root, "backend"),
    env: { ...process.env, DEMO_MODE: "0", DEMO_ADMIN: "0", USE_MOCK_DB: "1", MONGODB_URI: "" },
    stdio: ["ignore", "ignore", "pipe"],
  });
  let log = "";
  server.stderr.on("data", (d) => (log = (log + d).slice(-4000)));
  for (let i = 0; i < 120; i++) {
    try {
      const r = await fetch(`${BASE}/api/health`);
      if (r.ok) return;
    } catch {
      /* not up yet */
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`API didn't start:\n${log}`);
}

if (!process.env.QA_ACCOUNTS_BASE) await startServer();
const health = await fetch(`${BASE}/api/health`).then((r) => r.json());
if (health.demo_mode) throw new Error("These journeys need demo mode off (DEMO_MODE=0).");

const results = [];
const errors = [];
async function step(name, page, fn) {
  try {
    await fn();
    results.push(["PASS", name]);
  } catch (e) {
    results.push(["FAIL", name, String(e).split("\n")[0]]);
    mkdirSync(join(here, "report"), { recursive: true });
    await page.screenshot({ path: join(here, "report", `accounts-fail-${results.length}.png`), fullPage: true }).catch(() => {});
  }
}

const executablePath = process.env.PW_CHROMIUM_PATH;
const browser = await chromium.launch(executablePath ? { executablePath } : {});
const run = Date.now().toString(36);

for (const width of [390, 1280]) {
  const viewport = { width, height: width === 390 ? 844 : 900 };
  const newPage = async () => {
    const ctx = await browser.newContext({ viewport, isMobile: width === 390, hasTouch: width === 390 });
    const p = await ctx.newPage();
    p.on("pageerror", (e) => errors.push(`${width}: ${e}`));
    return p;
  };
  const creator = await newPage();
  const brand = await newPage();
  const tag = `${run}${width}`;
  const creatorName = `Kavya Kitchen ${tag}`;
  const campaign = `Pongal masala reels ${tag}`;

  await step(`${width}px: no demo sign-in or personas when demo mode is off`, creator, async () => {
    await creator.goto(`${BASE}/login?role=creator`);
    await creator.getByRole("heading", { name: "Sign in", exact: true }).waitFor();
    if (await creator.getByText("Or explore a demo profile").count()) throw new Error("demo profiles shown");
    const r = await fetch(`${BASE}/api/auth/personas`);
    if (r.status !== 404) throw new Error(`personas answered ${r.status}`);
  });

  await step(`${width}px: a creator signs up with email, onboards, and stays signed in after a reload`, creator, async () => {
    await creator.getByRole("button", { name: "Create an account" }).click();
    await creator.getByLabel("Your name or channel name").fill(creatorName);
    await creator.getByLabel("Email").fill(`creator-${tag}@example.test`);
    await creator.getByLabel("Password").fill("a long qa password");
    await creator.getByRole("button", { name: "Create account" }).click();
    await creator.waitForURL(/\/creator\/onboarding/);
    await creator.getByLabel("Your name or channel name").fill(creatorName);
    await creator.getByRole("checkbox", { name: "Food and cooking" }).click();
    await creator.getByRole("button", { name: "Next" }).click();
    await creator.getByRole("radio", { name: /1K to 10K/ }).click();
    await creator.getByLabel("Exact follower count (optional)").fill("4200");
    await creator.getByRole("button", { name: "Next" }).click();
    await creator.getByRole("checkbox", { name: "Brand collaborations" }).click();
    await creator.getByRole("button", { name: "Next" }).click();
    await creator.getByRole("checkbox", { name: /Tamil/ }).click();
    await creator.getByLabel("City", { exact: true }).selectOption("Chennai");
    await creator.getByRole("button", { name: "Next" }).click();
    if (await creator.getByText("Fill in sample insights (demo)").count()) throw new Error("demo-only switch shown");
    await creator.getByRole("button", { name: "Build my plan" }).click();
    await creator.getByRole("heading", { name: "Here's what to do this week" }).waitFor();
    await creator.reload();
    await creator.getByRole("heading", { name: "Here's what to do this week" }).waitFor();
  });

  await step(`${width}px: profile edits persist after a reload`, creator, async () => {
    await creator.goto(`${BASE}/creator/profile`);
    await creator.getByLabel("Content categories").fill("South Indian breakfasts, festival sweets");
    await creator.getByRole("button", { name: "Save profile" }).click();
    await creator.getByText("Profile saved").waitFor();
    await creator.reload();
    await creator.getByLabel("Content categories").waitFor();
    if ((await creator.getByLabel("Content categories").inputValue()) !== "South Indian breakfasts, festival sweets") throw new Error("categories didn't persist");
  });

  await step(`${width}px: Money, Roadmap and Opportunities open on a new marketplace (no verified brands)`, creator, async () => {
    for (const path of ["money", "roadmap", "opportunities"]) {
      await creator.goto(`${BASE}/creator/${path}`);
      await creator.getByRole("heading", { level: 1 }).first().waitFor();
      if (await creator.getByText("We couldn't load this").count()) throw new Error(`${path} failed to load`);
    }
  });

  await step(`${width}px: a brand signs up, saves a campaign draft, and publishes it; both survive a reload`, brand, async () => {
    await brand.goto(`${BASE}/login?role=brand`);
    await brand.getByRole("button", { name: "Create an account" }).click();
    await brand.getByLabel("Your name").fill("Asha Raman");
    await brand.getByLabel("Email").fill(`brand-${tag}@example.test`);
    await brand.getByLabel("Password").fill("a long qa password");
    await brand.getByRole("button", { name: "Create account" }).click();
    await brand.waitForURL(/\/brand\/onboarding/);
    await brand.getByLabel("Brand name").fill(`Thayir Foods ${tag}`);
    await brand.getByLabel("Category").fill("Masala and spices");
    await brand.getByRole("group", { name: "Niches" }).getByRole("checkbox", { name: "Food and cooking" }).click();
    await brand.getByRole("group", { name: "Languages" }).getByRole("checkbox", { name: /Tamil/ }).first().click();
    await brand.getByRole("button", { name: "Continue to your first campaign" }).click();
    await brand.waitForURL(/\/brand\/campaigns\/new/);
    await brand.getByLabel("Title").fill(campaign);
    await brand.getByLabel("Brief", { exact: true }).fill("Two reels cooking a Pongal dish with our masala, in Tamil.");
    await brand.getByRole("group", { name: "Objectives" }).getByRole("checkbox", { name: "Product launch" }).click();
    await brand.getByRole("group", { name: "Niches" }).getByRole("checkbox", { name: "Food and cooking" }).click();
    await brand.getByRole("group", { name: "Languages" }).getByRole("checkbox", { name: /Tamil/ }).first().click();
    await brand.getByRole("group", { name: "Audience ages" }).getByRole("checkbox", { name: "25-34" }).click();
    await brand.getByLabel("Deadline").fill("2027-01-10");
    await brand.getByRole("button", { name: "Save draft" }).click();
    await brand.waitForURL(/\/brand\/campaigns\/lst_/);
    await brand.reload();
    await brand.getByRole("heading", { name: campaign }).waitFor();
    await brand.getByText("Draft", { exact: true }).first().waitFor();
    await brand.getByRole("button", { name: "Publish" }).click();
    await brand.getByText("Campaign live").waitFor();
    await brand.reload();
    await brand.getByRole("button", { name: "Pause" }).waitFor(); // only a live campaign can be paused
  });

  await step(`${width}px: the creator applies; the application survives a reload`, creator, async () => {
    await creator.goto(`${BASE}/creator/opportunities`);
    const card = creator.getByRole("article").filter({ hasText: campaign });
    await card.getByRole("button", { name: "Apply" }).click();
    await creator.getByRole("button", { name: "Apply and share" }).click();
    await creator.getByText(/Applied to/).first().waitFor();
    await creator.reload();
    await creator.getByRole("article").filter({ hasText: campaign }).getByText("Applied").waitFor();
  });

  await step(`${width}px: the brand sends an offer; the creator signs it; both survive a reload`, brand, async () => {
    await brand.reload();
    await brand.getByRole("tab", { name: "Applications" }).click();
    await brand.getByRole("tabpanel", { name: "Applications" }).getByText(creatorName).waitFor();
    await brand.getByRole("tab", { name: /Matches/ }).click();
    await brand.getByRole("listitem").filter({ hasText: creatorName }).getByRole("button", { name: "Offer" }).click();
    await brand.getByRole("button", { name: "Send offer" }).click();
    await brand.getByText(/Offer sent to/).waitFor();
    await creator.goto(`${BASE}/creator/deals`);
    await creator.getByRole("link").filter({ hasText: `Thayir Foods ${tag}` }).first().click();
    await creator.getByRole("button", { name: /Accept .* and sign/ }).click();
    await creator.getByRole("dialog").getByRole("button", { name: /Accept .* and sign/ }).click();
    await creator.getByText(/E-signed/).first().waitFor();
    await creator.reload();
    await creator.getByText(/E-signed/).first().waitFor(); // the signature was saved
    await brand.goto(`${BASE}/brand/deals`);
    await brand.getByText(creatorName).first().waitFor();
  });

  await step(`${width}px: signing out ends the session`, creator, async () => {
    await creator.goto(`${BASE}/creator/profile`);
    if (width === 390) await creator.getByRole("button", { name: "More" }).click(); // the phone keeps it in the More sheet
    await creator.getByRole("button", { name: "Sign out" }).first().click();
    await creator.waitForURL(/\/login/);
    await creator.goto(`${BASE}/creator`);
    await creator.waitForURL(/\/login\?role=creator/);
  });

  await creator.context().close();
  await brand.context().close();
}

await browser.close();
server?.kill();
for (const [s, n, e] of results) console.log(`${s}  ${n}${e ? `  ${e}` : ""}`);
if (errors.length) console.log(`\nPage errors:\n${errors.join("\n")}`);
process.exit(results.some((r) => r[0] === "FAIL") || errors.length ? 1 : 0);
