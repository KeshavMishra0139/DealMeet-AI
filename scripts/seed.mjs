#!/usr/bin/env node
// `npm run seed -- [--reset] [--confirm-reset]`: runs scripts/seed.py with the API's Python.
import { spawnSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const python = process.platform === "win32" ? join(root, "backend", ".venv", "Scripts", "python.exe") : join(root, "backend", ".venv", "bin", "python");
const r = spawnSync(python, [join(root, "scripts", "seed.py"), ...process.argv.slice(2)], { stdio: "inherit" });
process.exit(r.status ?? 1);
