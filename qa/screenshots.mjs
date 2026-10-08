#!/usr/bin/env node
// Screenshot QA: visits every screen at 390 px (phone) and 1440 px (desktop),
// saves full-page screenshots, runs an axe-core accessibility audit, checks the
// rendered text against the copy rules, and records console errors.
// Only ever visits the local app (localhost).
//
//   node qa/screenshots.mjs                 # all routes
//   node qa/screenshots.mjs /creator /brand # only these
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const require = createRequire(import.meta.url);
const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..");
const BASE = process.env.QA_BASE ?? "http://localhost:5173";
if (!/^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(BASE)) throw new Error("QA only runs against localhost");

const ROUTES = [
  ["landing", "/"],
  ["login", "/login"],
  ["login-brand", "/login?role=brand"],
  ["creator-onboarding", "/creator/onboarding"],
  ["creator-home", "/creator?as=cr_a"],
  ["creator-home-b", "/creator?as=cr_b"],
  ["creator-roadmap", "/creator/roadmap?as=cr_a"],
  ["creator-money", "/creator/money?as=cr_a"],
  ["creator-opportunities", "/creator/opportunities?as=cr_a"],
  ["creator-deals", "/creator/deals?as=cr_a"],
  ["creator-kit", "/creator/kit?as=cr_a"],
  ["creator-privacy", "/creator/privacy?as=cr_a"],
  ["link-in-bio", "/c/creator.a"],
  ["brand-onboarding", "/brand/onboarding"],
  ["brand-home", "/brand?as=br_senpai"],
  ["brand-campaigns", "/brand/campaigns?as=br_senpai"],
  ["brand-new-campaign", "/brand/campaigns/new?as=br_senpai"],
  ["brand-campaign", "/brand/campaigns/lst_senpai_hoodie?as=br_senpai"],
  ["brand-collective", "/brand/campaigns/lst_thalam_collective?as=br_thalam"],
  ["brand-creator", "/brand/creators/cr_a?as=br_senpai&listing=lst_senpai_hoodie"],
  ["brand-creator-locked", "/brand/creators/cr_b?as=br_senpai"],
  ["brand-deals", "/brand/deals?as=br_senpai"],
  ["demo-compare", "/demo/compare"],
  ["demo-live", "/demo/live"],
  ["not-found", "/this-does-not-exist"],
];
const VIEWPORTS = [
  { name: "390", width: 390, height: 844, isMobile: true, deviceScaleFactor: 2 },
  { name: "1440", width: 1440, height: 900, isMobile: false, deviceScaleFactor: 1 },
];

const only = process.argv.slice(2);
const routes = only.length ? ROUTES.filter(([, p]) => only.some((o) => p.startsWith(o))) : ROUTES;
const rules = JSON.parse(readFileSync(join(root, "shared", "copy-rules.json"), "utf8")).banned.map(
  (r) => new RegExp(r.pattern, "i"),
);
const axePath = require.resolve("axe-core/axe.min.js");

async function launch() {
  try {
    return await chromium.launch();
  } catch {
    return await chromium.launch({ executablePath: "/opt/pw-browsers/chromium" });
  }
}

const browser = await launch();
const report = [];
for (const vp of VIEWPORTS) {
  const dir = join(here, "shots", vp.name);
  mkdirSync(dir, { recursive: true });
  const context = await browser.newContext({
    viewport: { width: vp.width, height: vp.height },
    deviceScaleFactor: vp.deviceScaleFactor,
    isMobile: vp.isMobile,
    hasTouch: vp.isMobile,
    reducedMotion: "reduce",
  });
  for (const [name, path] of routes) {
    const page = await context.newPage();
    const errors = [];
    page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
    page.on("pageerror", (e) => errors.push(String(e)));
    await page.goto(BASE + path, { waitUntil: "networkidle" });
    await page.waitForTimeout(500);
    await page.screenshot({ path: join(dir, `${name}.png`), fullPage: true });

    const text = await page.evaluate(() => document.body.innerText);
    const copy = rules.filter((rx) => rx.test(text)).map(String);
    await page.addScriptTag({ path: axePath });
    const axe = await page.evaluate(async () => {
      // eslint-disable-next-line no-undef
      const r = await axe.run(document, { runOnly: ["wcag2a", "wcag2aa", "best-practice"] });
      return r.violations.map((v) => ({
        id: v.id,
        impact: v.impact,
        help: v.help,
        nodes: v.nodes.slice(0, 4).map((n) => n.target.join(" ")),
        count: v.nodes.length,
      }));
    });
    const hScroll = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
    report.push({ viewport: vp.name, name, path, errors, copy, axe, hScroll });
    const flag = (cond, s) => (cond ? s : "");
    console.log(
      `${vp.name.padStart(4)}  ${name.padEnd(24)} ${flag(errors.length, `console:${errors.length} `)}${flag(
        copy.length,
        `COPY:${copy.join(",")} `,
      )}${flag(axe.length, `a11y:${axe.map((a) => `${a.id}(${a.count})`).join(",")} `)}${flag(hScroll, "H-SCROLL")}`,
    );
    await page.close();
  }
  await context.close();
}
await browser.close();
mkdirSync(join(here, "report"), { recursive: true });
writeFileSync(join(here, "report", "qa.json"), JSON.stringify(report, null, 2));
const bad = report.filter((r) => r.copy.length || r.hScroll || r.axe.some((a) => ["critical", "serious"].includes(a.impact)));
console.log(`\n${report.length} screenshots in qa/shots. ${bad.length} screen(s) need attention. Details: qa/report/qa.json`);
