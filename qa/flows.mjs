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
const mobile = page;
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

await step("Campaigns: a draft lists what's missing, then publish, pause and resume", async () => {
  await reset();
  await page.goto(`${BASE}/brand/campaigns/new?as=br_senpai`);
  await page.getByLabel("Title").fill("QA festive anime drop");
  await page.getByRole("button", { name: "Save draft" }).click();
  await page.waitForURL(/\/brand\/campaigns\/lst_/);
  await page.getByText("Before it can go live").waitFor();
  await page.getByRole("link", { name: "Edit" }).click();
  await page.getByLabel("Brief", { exact: true }).fill("Two reels showing the festive drop, posted before Diwali.");
  await page.getByRole("group", { name: "Objectives" }).getByRole("checkbox", { name: "Product launch" }).click();
  await page.getByRole("group", { name: "Niches" }).getByRole("checkbox", { name: "Anime edits" }).click();
  await page.getByRole("group", { name: "Languages" }).getByRole("checkbox", { name: /Hindi/ }).first().click();
  await page.getByRole("group", { name: "Audience ages" }).getByRole("checkbox", { name: "18-24" }).click();
  await page.getByLabel("Deadline").fill("2026-12-15");
  await page.getByRole("button", { name: "Save changes" }).click();
  await page.getByRole("button", { name: "Publish" }).click();
  await page.getByText("Campaign live").waitFor();
  await page.getByRole("button", { name: "Pause" }).click();
  await page.getByText(/Paused: no new applications/).first().waitFor();
  await page.getByRole("button", { name: "Resume" }).click();
  await page.getByText("Live again.").waitFor();
  await page.getByRole("tab", { name: "Applications" }).click();
  await page.getByText(/No applications yet/).waitFor();
});

await step("Shortlist: save two matches with a note, compare them, then send a drafted offer only after confirming", async () => {
  await reset();
  await page.goto(`${BASE}/brand/campaigns/lst_senpai_hoodie?as=br_senpai`);
  await page.getByRole("button", { name: "Shortlist Kabir Malhotra" }).click();
  await page.getByRole("button", { name: "Remove Kabir Malhotra from the shortlist" }).waitFor();
  await page.getByRole("button", { name: "Shortlist Ishaan Mehta" }).click();
  await page.getByRole("button", { name: "Remove Ishaan Mehta from the shortlist" }).waitFor();
  await page.getByRole("button", { name: "Why ranked here" }).first().click();
  await page.getByText("Limits of this data").waitFor();
  await page.keyboard.press("Escape");
  await page.getByRole("tab", { name: "Shortlist" }).click();
  await page.getByLabel("Note about Kabir Malhotra").fill("Ask about the Diwali drop");
  await page.getByLabel("Note about Kabir Malhotra").press("Enter");
  await page.getByRole("checkbox", { name: "Compare Kabir Malhotra" }).click();
  await page.getByRole("checkbox", { name: "Compare Ishaan Mehta" }).click();
  await page.getByRole("button", { name: "Compare 2" }).click();
  await page.getByRole("rowheader", { name: "Estimated price" }).waitFor();
  await page.getByText("Ask about the Diwali drop").waitFor();
  await page.getByRole("tab", { name: "Shortlist" }).click();
  await page.locator("li", { hasText: "Kabir Malhotra" }).getByRole("button", { name: "Draft offer" }).click();
  await page.getByText("Draft · not sent").waitFor();
  await page.getByRole("button", { name: "Review and send" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Confirm and send" }).click();
  await page.getByText(/Offer sent to Kabir Malhotra/).waitFor();
});

await step("Brands: search the directory, save a Dream Brand, see it in the Studio; unclaimed pages say they aren't on JodiDar", async () => {
  await reset();
  await page.goto(`${BASE}/brands?as=cr_a`);
  await page.getByLabel("Search").fill("senpai");
  await page.getByRole("link", { name: /Senpai Supply Co\./ }).click();
  await page.getByRole("heading", { name: "Senpai Supply Co." }).waitFor();
  await page.getByText(/creators? with connected accounts want to work with this brand/).waitFor();
  await page.getByRole("button", { name: "Save as Dream Brand" }).click();
  await page.getByText(/saved to your Dream Brands/).waitFor();
  await page.goto(`${BASE}/creator/brands?as=cr_a`);
  await page.getByText("Senpai Supply Co.").first().waitFor();
  await page.goto(`${BASE}/brands/notebook-nagar`);
  await page.getByText("Not on JodiDar AI and not affiliated with us.").first().waitFor();
  await page.getByRole("button", { name: "Request removal" }).waitFor();
});

await step("Pitch: a creator writes a pitch from their own numbers and sends it; the brand accepts it from the Fan Inbox", async () => {
  await reset();
  await page.goto(`${BASE}/brands/thalam-foods?as=cr_b`);
  await page.getByRole("link", { name: "Pitch this brand" }).click();
  await page.getByRole("button", { name: "Write my pitch to Thalam Foods" }).click();
  await page.getByRole("heading", { name: /Pitch to Thalam Foods/ }).waitFor();
  await page.getByText("Numbers it can use").waitFor();
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Confirm" }).click();
  await page.getByText("Sent to Thalam Foods").waitFor();
  await page.goto(`${BASE}/brand/inbox?as=br_thalam`);
  await page.getByRole("heading", { name: "Fan Inbox" }).waitFor();
  await page.getByRole("button", { name: "Accept" }).first().click();
  await page.getByRole("dialog").getByRole("button", { name: "Send offer" }).click();
  await page.getByText(/Offer sent to/).waitFor();
});

await step("Public page: write a positioning, show it on the page with badges, an estimate and a QR code", async () => {
  await reset();
  await page.goto(`${BASE}/creator/kit?as=cr_a`);
  await page.getByRole("button", { name: "Write my positioning" }).click();
  await page.getByText("Content pillars").waitFor();
  await page.getByLabel("Positioning", { exact: true }).fill("Anime edits people rewatch, in Hindi and English");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await page.getByText("Positioning saved").first().waitFor();
  await page.getByRole("switch", { name: "Show the positioning on my public page" }).click();
  await page.goto(`${BASE}/c/creator.a`);
  await page.getByText("Anime edits people rewatch, in Hindi and English").waitFor();
  await page.getByText(/Estimated range/).first().waitFor();
  await page.getByRole("img", { name: /QR code for Creator A/ }).waitFor();
  await page.getByRole("link", { name: "Download QR" }).waitFor();
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
  await page.getByRole("dialog").getByRole("button", { name: "Submit", exact: true }).click();
  await page.getByRole("button", { name: "Remind the brand" }).waitFor();
  await page.goto(`${BASE}/brand/deals/dl_a_senpai?as=br_senpai`);
  await page.getByText("The post is public and live").waitFor(); // automatic checks: not checked without a connected account
  await page.getByRole("button", { name: "Approve post" }).click();
  await page.getByText(/Simulated payout of .* No money moved/).first().waitFor();
  await page.getByRole("link", { name: /Invoice JD-/ }).waitFor();
});

await step("Contract: the creator proposes new terms, the brand accepts that version, and both see it agreed with its hash", async () => {
  await reset();
  await page.goto(`${BASE}/creator/deals/dl_b_tiffin?as=cr_b`);
  await page.getByRole("button", { name: "Propose changes" }).click();
  await page.getByLabel("Fee (₹)").fill("2500");
  await page.getByLabel("Stories").fill("2");
  await page.getByRole("button", { name: "Send proposal" }).click();
  await page.getByText("Negotiating").first().waitFor();
  await page.goto(`${BASE}/brand/deals/dl_b_tiffin?as=pg_tiffin`);
  await page.getByRole("button", { name: /Accept .* and sign/ }).click();
  await page.getByRole("dialog").getByRole("button", { name: /Accept .* and sign/ }).click();
  await page.getByText("Contract agreed").first().waitFor();
  await page.getByText("Version 2", { exact: true }).waitFor();
  await page.getByText("Agreed", { exact: true }).waitFor();
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

await step("Profile: edit the bio and preferences; completeness rises and it persists after a reload", async () => {
  await reset();
  await page.goto(`${BASE}/creator/profile?as=cr_b`);
  const ring = page.locator("section[aria-labelledby=complete]");
  const before = Number(await ring.locator(".num").first().innerText());
  await page.getByLabel("Content categories").fill("quick breakfasts, ragi recipes");
  await page.getByLabel("Minimum fee (₹)").fill("1500");
  await page.getByRole("button", { name: "Save profile" }).click();
  await page.getByText("Profile saved").waitFor();
  await page.reload();
  await page.getByLabel("Content categories").waitFor();
  if ((await page.getByLabel("Content categories").inputValue()) !== "quick breakfasts, ragi recipes") throw new Error("categories didn't persist");
  const after = Number(await ring.locator(".num").first().innerText());
  if (!(after > before)) throw new Error(`completeness ${before} -> ${after}`);
  await page.locator("section[aria-labelledby=ready]").getByText("connect to check").first().waitFor();
});

await step("Coach: ask about views, see the numbers used with their sources, then make a plan", async () => {
  await reset();
  await page.goto(`${BASE}/creator?as=cr_a`);
  await page.getByRole("button", { name: "Ask about your numbers" }).first().click();
  const dlg = page.getByRole("dialog");
  await dlg.getByRole("button", { name: "Are my views growing?" }).click();
  await dlg.getByText("Numbers used").waitFor();
  await dlg.getByText("What's uncertain:").waitFor();
  await dlg.getByText(/Self-reported|Sample data|Live data/).first().waitFor();
  await dlg.getByRole("button", { name: "Make me a plan" }).click();
  await page.getByText(/Plan saved: 3 goals/).waitFor();
  await page.keyboard.press("Escape");
  await page.getByRole("heading", { name: "Your goals" }).waitFor();
});

await step("Rates and media kit: save your rate next to the estimate, save a Hindi kit version, show it on the public page", async () => {
  await reset();
  await page.goto(`${BASE}/creator/money?as=cr_a`);
  await page.getByText("Missing, not guessed").or(page.getByText("Numbers used")).first().waitFor();
  await page.getByLabel("Your rate (₹)").fill("21000");
  await page.getByRole("button", { name: "Save as your rate" }).click();
  await page.getByText("Estimated range", { exact: true }).first().waitFor();
  await page.getByText("₹21,000").first().waitFor();
  await page.goto(`${BASE}/creator/kit?as=cr_a`);
  await page.getByRole("radio", { name: "हिंदी" }).click();
  await page.getByText("फ़ॉलोअर्स").first().waitFor();
  await page.getByLabel("Headline").fill("हिंदी और अंग्रेज़ी में एनिमे एडिट्स");
  await page.getByRole("button", { name: /Save as version/ }).click();
  await page.getByText("Version 1 saved").waitFor();
  await page.getByRole("button", { name: "Show version 1 on your public page" }).click();
  await page.getByText("On your public page").waitFor();
  await page.goto(`${BASE}/c/creator.a`);
  await page.getByText("हिंदी और अंग्रेज़ी में एनिमे एडिट्स", { exact: true }).waitFor();
  await page.getByText(/वर्शन 1/).waitFor();
});

await step("Hindi toggle: moves, stage and rate gap switch to Hindi", async () => {
  await reset();
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

await step("What am I worth?: public page says plainly when YouTube data isn't connected", async () => {
  page = mobile;
  await page.goto(`${BASE}/worth`);
  await page.getByLabel("YouTube handle or channel link").fill("@somechannel");
  await page.getByRole("button", { name: "Check my price" }).click();
  // No YOUTUBE_API_KEY on the QA server: a clear "not connected" message, never made-up numbers.
  await page.getByRole("alert").getByText(/YouTube data isn't connected on this server/).waitFor();
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
