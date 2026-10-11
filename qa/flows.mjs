#!/usr/bin/env node
// End-to-end checks of the demo's key journeys, by clicking through the real UI.
// Only ever visits the local app (localhost). Run with `make dev` running:
//   node qa/flows.mjs
import { mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const here = dirname(fileURLToPath(import.meta.url));

const BASE = process.env.QA_BASE ?? "http://localhost:5173";
const API = process.env.QA_API ?? "http://localhost:8000";
if (!/^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(BASE)) throw new Error("QA only runs against localhost");

const results = [];
let page;
async function step(name, fn) {
  try {
    await fn();
    results.push(["PASS", name]);
  } catch (e) {
    results.push(["FAIL", name, String(e).split("\n")[0]]);
    try {
      mkdirSync(join(here, "report"), { recursive: true });
      await page.screenshot({ path: join(here, "report", `fail-${results.length}.png`), fullPage: true });
    } catch {
      /* page may be closed */
    }
  }
}

async function launch() {
  // PW_CHROMIUM_PATH points at a Chromium installed outside Playwright, if any.
  const executablePath = process.env.PW_CHROMIUM_PATH;
  try {
    return await chromium.launch(executablePath ? { executablePath } : {});
  } catch (e) {
    console.error("Could not start Chromium. Run this once: npx playwright install chromium");
    throw e;
  }
}

// Writes need the app's header (CSRF guard); private reads need a session.
const reset = () => fetch(`${API}/api/demo/reset`, { method: "POST", headers: { "X-Requested-With": "qa" } });
async function apiAs(persona, path) {
  const login = await fetch(`${API}/api/auth/demo`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Requested-With": "qa" },
    body: JSON.stringify({ persona, cookie: false }),
  }).then((r) => r.json());
  return fetch(`${API}${path}`, { headers: { Authorization: `Bearer ${login.token}` } }).then((r) => r.json());
}

await reset();
const browser = await launch();
page = await browser.newPage({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));

await step("Sign-in gate: Creator Studio sends you to sign in", async () => {
  await page.goto(`${BASE}/creator`);
  await page.waitForURL(/\/login\?role=creator/);
  await page.getByRole("heading", { name: "Sign in", exact: true }).waitFor();
});

await step("Onboarding: 5 steps create a plan", async () => {
  await page.goto(`${BASE}/login?role=creator`);
  await page.getByRole("button", { name: /New creator/ }).click();
  await page.waitForURL(/\/creator\/onboarding/);
  await page.getByLabel("Your name or channel name").fill("Meera Test Kitchen");
  await page.getByRole("checkbox", { name: "Food and cooking" }).click();
  await page.getByRole("button", { name: "Next" }).click();
  await page.getByRole("radio", { name: /1K to 10K/ }).click();
  await page.getByLabel("Exact follower count (optional)").fill("3400");
  await page.getByRole("button", { name: "Next" }).click();
  await page.getByRole("checkbox", { name: "Digital products" }).click();
  await page.getByRole("button", { name: "Next" }).click();
  await page.getByRole("checkbox", { name: /Tamil/ }).click();
  await page.getByLabel("City", { exact: true }).selectOption("Chennai");
  await page.getByLabel(/Paste 2 or 3/).fill("10 நிமிடத்தில் ரவா உப்புமா\nதக்காளி சட்னி");
  await page.getByRole("button", { name: "Read my captions" }).click();
  await page.getByText("Brand safe").first().waitFor();
  await page.getByRole("button", { name: "Next" }).click();
  await page.getByText("Not connected yet. Connect after setup.").first().waitFor();
  await page.getByRole("switch", { name: "Fill in sample insights (demo)" }).click();
  await page.getByRole("button", { name: "Build my plan" }).click();
  await page.getByRole("heading", { name: "Here's what to do this week" }).waitFor();
  const cards = await page.getByRole("article").count();
  if (cards !== 3) throw new Error(`expected 3 moves, got ${cards}`);
});

await step("Creator A: mark a move done, then plan next week adapts", async () => {
  await page.goto(`${BASE}/creator?as=cr_a`);
  await page.getByRole("heading", { name: /Raise your reel rate/ }).waitFor();
  await page.getByRole("button", { name: "Mark done" }).first().click();
  await page.getByRole("radio", { name: "It worked" }).click();
  await page.getByLabel(/Rate agreed/).fill("17000");
  await page.getByRole("button", { name: "Save" }).click();
  await page.getByText(/Done · It worked/).waitFor();
  await page.getByRole("button", { name: "Plan next week" }).click();
  await page.getByText("What changed since last week").waitFor();
  await page.getByRole("heading", { name: /rate card to 3 past brands/ }).waitFor();
});

await step("Money: price changes per brand match", async () => {
  await reset();
  await page.goto(`${BASE}/creator/money?as=cr_a`);
  await page.getByText("₹17K–18K").first().waitFor();
  await page.getByRole("radio", { name: /Thalam Foods/ }).click();
  await page.getByText("₹12.5K–13K").first().waitFor();
});

await step("Why? popovers open with reasons", async () => {
  await page.goto(`${BASE}/creator?as=cr_a`);
  await page.getByRole("button", { name: /Why: Raise your reel rate/ }).click();
  await page.getByText("Why raise your rate").waitFor();
  await page.getByText(/Depends on simulated data/).waitFor();
});

await step("Creator B opts in to the Thalam collective; the brand sees her in the pack", async () => {
  await reset();
  await page.goto(`${BASE}/creator/opportunities?as=cr_b`);
  await page.getByRole("radio", { name: /Collectives/ }).click();
  await page.getByRole("button", { name: "Opt in" }).first().click();
  await page.getByRole("button", { name: "Opt in and share" }).click();
  await page.getByText("Opted in").first().waitFor();
  await page.goto(`${BASE}/brand/campaigns/lst_thalam_collective?as=br_thalam`);
  const row = page.getByRole("row", { name: /Creator B/ });
  await row.getByText("Opted in").waitFor();
});

await step("Brand sends an offer from matches; it lands in the creator's pipeline", async () => {
  await page.goto(`${BASE}/brand/campaigns/lst_senpai_hoodie?as=br_senpai`);
  await page.getByRole("button", { name: "Offer" }).first().click();
  await page.getByRole("button", { name: "Send offer" }).click();
  await page.getByText(/Offer sent to/).waitFor();
  const r = await apiAs("cr_g01", "/api/creators/cr_g01/home");
  if (!r.pipeline) throw new Error("no pipeline");
});

await step("Privacy: revoking a brand logs it and hides the creator", async () => {
  await page.goto(`${BASE}/creator/privacy?as=cr_a`);
  await page.getByRole("button", { name: "Revoke" }).first().click();
  await page.getByText("Revoked", { exact: true }).first().waitFor();
  await page.getByText("access revoked").first().waitFor();
});

await step("Deal rail: counter a low offer, brand accepts, escrow, post, approve, simulated payout", async () => {
  await reset();
  await page.goto(`${BASE}/creator/deals/dl_a_senpai?as=cr_a`);
  await page.getByText(/58% below the fair price/).waitFor();
  await page.getByRole("button", { name: /Counter at/ }).click();
  await page.getByRole("button", { name: "Send counter" }).click();
  await page.getByText(/You countered at/).waitFor();
  await page.goto(`${BASE}/brand/deals/dl_a_senpai?as=br_senpai`);
  await page.getByRole("button", { name: /Accept .* and sign/ }).click();
  await page.getByRole("dialog").getByRole("button", { name: /Accept .* and sign/ }).click();
  await page.getByRole("button", { name: /Fund escrow/ }).click();
  await page.getByRole("button", { name: /Pay .*simulated/ }).click();
  await page.getByText(/in simulated escrow/).first().waitFor();
  await page.goto(`${BASE}/creator/deals/dl_a_senpai?as=cr_a`);
  await page.getByRole("button", { name: "Submit post link" }).click();
  await page.getByLabel(/Instagram reel or YouTube Short link/).fill("https://www.instagram.com/reel/DEMOA1/");
  await page.getByRole("dialog").getByRole("button", { name: "Submit link" }).click();
  await page.getByRole("button", { name: "Remind the brand" }).waitFor();
  await page.goto(`${BASE}/brand/deals/dl_a_senpai?as=br_senpai`);
  await page.getByText("The post is public and live").waitFor(); // automatic checks: not checked without a connected account
  await page.getByRole("button", { name: "Approve post" }).click();
  await page.getByText(/Simulated payout of .* No money moved/).first().waitFor();
  await page.getByRole("link", { name: /Invoice JD-/ }).waitFor();
});

await step("Link-in-bio: a brand books from the public page; it lands in the creator's deals", async () => {
  await page.goto(`${BASE}/c/creator.a`);
  await page.getByRole("button", { name: /Book Creator/ }).click();
  await page.getByLabel("Brand").fill("Otaku Threads");
  await page.getByLabel("Work email").fill("hello@otaku.test");
  await page.getByRole("button", { name: "Send booking request" }).click();
  await page.getByText("Request sent").waitFor();
  await page.goto(`${BASE}/creator/deals?as=cr_a`);
  await page.getByText("Otaku Threads").first().waitFor();
});

await step("Hindi toggle: moves, stage and rate gap switch to Hindi", async () => {
  await page.goto(`${BASE}/creator?as=cr_a&lang=en`);
  await page.getByRole("heading", { name: "Here's what to do this week" }).waitFor();
  await page.getByRole("button", { name: /Switch to Hindi/ }).click();
  await page.getByRole("heading", { name: "इस हफ़्ते क्या करना है" }).waitFor();
  await page.getByRole("heading", { name: /अपना रील रेट ₹17K–18K करें/ }).waitFor();
  await page.getByText("कमा रहे हैं, पर कम रेट पर").first().waitFor();
  await page.getByRole("button", { name: /Switch to English/ }).click();
  await page.getByRole("heading", { name: "Here's what to do this week" }).waitFor();
});

await step("Accounts: sign up as a brand, set up the brand, sign out", async () => {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const p = await ctx.newPage();
  p.on("pageerror", (e) => errors.push(String(e)));
  page = p;
  await p.goto(`${BASE}/login?role=brand`);
  await p.getByRole("button", { name: "Create an account" }).click();
  await p.getByLabel("Your name").fill("QA Brand Owner");
  await p.getByLabel("Email").fill(`qa-${Date.now()}@example.test`);
  await p.getByLabel("Password").fill("a long qa password");
  await p.getByRole("button", { name: "Create account" }).click();
  await p.waitForURL(/\/brand\/onboarding/);
  await p.getByLabel("Brand name").fill("QA Snacks");
  await p.getByLabel("Category").fill("Snacks");
  await p.getByRole("group", { name: "Niches" }).getByRole("checkbox", { name: "Food and cooking" }).click();
  await p.getByRole("group", { name: "Languages" }).getByRole("checkbox", { name: /Hindi/ }).first().click();
  await p.getByRole("button", { name: "Continue to your first campaign" }).click();
  await p.waitForURL(/\/brand\/campaigns\/new/);
  await p.goto(`${BASE}/brand`);
  await p.getByRole("heading", { name: "QA Snacks" }).waitFor(); // the session survives a reload (HttpOnly cookie)
  // A brand account can't open the Creator Studio.
  await p.goto(`${BASE}/creator`);
  await p.getByRole("heading", { name: /for a creator account/ }).waitFor();
  await p.getByRole("button", { name: "Sign out" }).click();
  await p.waitForURL(/\/login/);
  await p.goto(`${BASE}/brand`);
  await p.waitForURL(/\/login\?role=brand/);
  await ctx.close();
});

// Presenting on a laptop: compare, phone view and the live split.
const desk = await browser.newPage({ viewport: { width: 1440, height: 900 } });
desk.on("pageerror", (e) => errors.push(String(e)));
page = desk;

await step("Compare: guided demo steps through both creators with captions", async () => {
  await reset();
  await desk.goto(`${BASE}/demo/compare?phone=0`);
  await desk.getByText("Earning, underpriced").first().waitFor();
  await desk.getByText("Starting").first().waitFor();
  await desk.getByRole("button", { name: "Guided demo" }).click();
  const bar = desk.getByRole("region", { name: "Guided demo" });
  await bar.getByText("Step 1 of 7").waitFor();
  await desk.keyboard.press("ArrowRight");
  await desk.keyboard.press("ArrowRight");
  await bar.getByText("Step 3 of 7").waitFor();
  await bar.getByText(/Fair price ₹17K–18K a reel/).waitFor();
  await desk.keyboard.press("Escape");
  await bar.waitFor({ state: "detached" });
});

await step("Phone view: P puts the app in a 390 x 844 phone and back", async () => {
  await desk.goto(`${BASE}/creator?as=cr_b&phone=0`);
  await desk.getByRole("heading", { name: "Here's what to do this week" }).waitFor();
  await desk.keyboard.press("p");
  const phone = desk.frameLocator('iframe[title="JodiDar AI on a phone"]');
  await phone.getByRole("heading", { name: /Post 2 Tamil quick-breakfast reels/ }).waitFor();
  const box = await desk.locator('iframe[title="JodiDar AI on a phone"]').boundingBox();
  if (!box || Math.abs(box.width / box.height - 390 / (844 - 47 - 21)) > 0.02) throw new Error(`Unexpected frame size ${JSON.stringify(box)}`);
  await phone.getByRole("link", { name: "Money", exact: true }).click();
  await desk.waitForURL(/\/creator\/money/);
  await desk.getByRole("button", { name: "Exit phone view" }).click();
  await desk.getByRole("heading", { name: /Money paths/ }).waitFor();
});

await step("Live demo: a counter on the phone appears in the brand console without a reload", async () => {
  await reset();
  await desk.goto(`${BASE}/demo/live`);
  const phone = desk.frameLocator('iframe[title="Creator A\'s Creator Studio"]');
  const consoleFrame = desk.frameLocator('iframe[title="Senpai Supply Co. Brand Console"]');
  await consoleFrame.getByText(/58% below the fair price/).waitFor();
  await phone.getByRole("button", { name: /Counter at/ }).click();
  await phone.getByRole("button", { name: "Send counter" }).click();
  await consoleFrame.getByRole("button", { name: /Accept .* and sign/ }).waitFor({ timeout: 2500 });
  await desk.getByText(/Synced · Deal updated/).waitFor();
});

await step("3D: the reach chart and the match space draw with WebGL", async () => {
  await desk.goto(`${BASE}/creator?as=cr_a&phone=0`);
  const reach = desk.locator("section[aria-labelledby=reach]");
  await reach.scrollIntoViewIfNeeded();
  await reach.locator("canvas").waitFor();
  await desk.goto(`${BASE}/brand/campaigns/lst_senpai_hoodie?as=br_senpai`);
  const space = desk.locator("section[aria-labelledby=space]");
  await space.locator("canvas").waitFor();
  // A canvas starts at the browser's default 150 px and is sized on its first frame, so give it a moment.
  let height = 0;
  for (let i = 0; i < 20 && height < 300; i++) {
    height = (await space.locator("canvas").boundingBox())?.height ?? 0;
    if (height < 300) await desk.waitForTimeout(250);
  }
  if (height < 300) throw new Error(`Match space canvas too small (${Math.round(height)} px)`);
});

await browser.close();
for (const r of results) console.log(r.join("  "));
if (errors.length) console.log("Page errors:", errors);
process.exit(results.some((r) => r[0] === "FAIL") || errors.length ? 1 : 0);
