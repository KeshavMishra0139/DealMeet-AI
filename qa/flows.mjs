#!/usr/bin/env node
// End-to-end checks of the demo's key journeys, by clicking through the real UI.
// Only ever visits the local app (localhost). Run with `make dev` running:
//   node qa/flows.mjs
import { chromium } from "playwright";

const BASE = process.env.QA_BASE ?? "http://localhost:5173";
const API = process.env.QA_API ?? "http://localhost:8000";
if (!/^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(BASE)) throw new Error("QA only runs against localhost");

const results = [];
async function step(name, fn) {
  try {
    await fn();
    results.push(["PASS", name]);
  } catch (e) {
    results.push(["FAIL", name, String(e).split("\n")[0]]);
  }
}

async function launch() {
  try {
    return await chromium.launch();
  } catch {
    return await chromium.launch({ executablePath: "/opt/pw-browsers/chromium" });
  }
}

await fetch(`${API}/api/demo/reset`, { method: "POST" });
const browser = await launch();
const page = await browser.newPage({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));

await step("Onboarding: 5 steps create a plan", async () => {
  await page.goto(`${BASE}/creator/onboarding`);
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
  await page.getByRole("button", { name: /Instagram/ }).click();
  await page.getByRole("button", { name: "Allow" }).click();
  await page.getByText("Connected (demo sandbox)").waitFor();
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
  await fetch(`${API}/api/demo/reset`, { method: "POST" });
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

await browser.close();
for (const r of results) console.log(r.join("  "));
if (errors.length) console.log("Page errors:", errors);
process.exit(results.some((r) => r[0] === "FAIL") || errors.length ? 1 : 0);
