#!/usr/bin/env node
// Runs every check that guards the demo: API tests (engines, copy rules,
// no-scraping), web copy rules, and the TypeScript build.
import { spawnSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const isWin = process.platform === "win32";
const venvPython = isWin
  ? join(root, "backend", ".venv", "Scripts", "python.exe")
  : join(root, "backend", ".venv", "bin", "python");

const steps = [
  ["API tests", venvPython, ["-m", "pytest", "-q"], join(root, "backend")],
  ["Copy rules (web)", "npm", ["run", "check:copy"], join(root, "frontend")],
  ["Type check (web)", "npm", ["run", "typecheck"], join(root, "frontend")],
];

let failed = false;
for (const [name, cmd, args, cwd] of steps) {
  console.log(`\n== ${name}`);
  // npm is npm.cmd on Windows and needs cmd.exe; python.exe is started directly so
  // a project path with spaces still works.
  const r = spawnSync(cmd, args, { cwd, stdio: "inherit", shell: isWin && cmd === "npm" });
  if (r.status !== 0) {
    failed = true;
    console.error(`!! ${name} failed`);
  }
}
process.exit(failed ? 1 : 0);
