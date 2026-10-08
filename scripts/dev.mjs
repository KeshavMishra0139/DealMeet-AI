#!/usr/bin/env node
// One command to run JodiDar AI locally: installs what's missing on first run,
// then starts the API (FastAPI, :8000) and the web app (Vite, :5173) together.
// Works on macOS, Linux and Windows with only Node 20+ and Python 3.10+.
import { spawn, spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const backend = join(root, "backend");
const frontend = join(root, "frontend");
const isWin = process.platform === "win32";
const setupOnly = process.argv.includes("--setup-only");
// --single-port: build the web app once and serve everything from the API on :8000
// (closest to a deployed demo; no hot reload).
const singlePort = process.argv.includes("--single-port");

const c = (code) => (s) => (process.stdout.isTTY ? `\x1b[${code}m${s}\x1b[0m` : s);
const magenta = c("35");
const cyan = c("36");
const dim = c("2");
const bold = c("1");

function log(msg) {
  console.log(`${magenta("jodidar")} ${msg}`);
}

function findPython() {
  const candidates = isWin ? [["py", ["-3"]], ["python", []]] : [["python3", []], ["python", []]];
  for (const [cmd, pre] of candidates) {
    const r = spawnSync(cmd, [...pre, "-c", "import sys; print(sys.version_info >= (3, 10))"], {
      encoding: "utf8",
    });
    if (r.status === 0 && r.stdout.trim() === "True") return [cmd, pre];
  }
  return null;
}

function run(cmd, args, opts = {}) {
  const r = spawnSync(cmd, args, { stdio: "inherit", shell: isWin, ...opts });
  if (r.status !== 0) {
    console.error(`\n${magenta("jodidar")} command failed: ${cmd} ${args.join(" ")}`);
    process.exit(r.status ?? 1);
  }
}

function hashFile(p) {
  return createHash("sha1").update(readFileSync(p)).digest("hex");
}

const venvPython = isWin
  ? join(backend, ".venv", "Scripts", "python.exe")
  : join(backend, ".venv", "bin", "python");

function ensureBackend() {
  const reqs = join(backend, "requirements.txt");
  const stamp = join(backend, ".deps-stamp");
  if (!existsSync(venvPython)) {
    const py = findPython();
    if (!py) {
      console.error("Python 3.10+ is required. Install it from python.org and run again.");
      process.exit(1);
    }
    log("creating Python virtual environment (first run only)");
    run(py[0], [...py[1], "-m", "venv", join(backend, ".venv")]);
  }
  const want = hashFile(reqs);
  const have = existsSync(stamp) ? readFileSync(stamp, "utf8").trim() : "";
  if (want !== have) {
    log("installing API dependencies");
    run(venvPython, ["-m", "pip", "install", "--disable-pip-version-check", "-q", "-r", reqs]);
    writeFileSync(stamp, want);
  }
}

function ensureFrontend() {
  const lock = join(frontend, "package-lock.json");
  const stamp = join(frontend, "node_modules", ".deps-stamp");
  const want = existsSync(lock) ? hashFile(lock) : "none";
  const have = existsSync(stamp) ? readFileSync(stamp, "utf8").trim() : "";
  if (!existsSync(join(frontend, "node_modules")) || want !== have) {
    log("installing web dependencies");
    run("npm", ["install", "--no-audit", "--no-fund"], { cwd: frontend });
    writeFileSync(stamp, want);
  }
}

ensureBackend();
ensureFrontend();
if (setupOnly) {
  log("setup complete");
  process.exit(0);
}

const procs = [];
function start(name, color, cmd, args, cwd) {
  const p = spawn(cmd, args, { cwd, shell: isWin, env: { ...process.env, FORCE_COLOR: "1" } });
  const tag = color(name.padEnd(4));
  const pipe = (stream) => {
    let buf = "";
    stream.on("data", (d) => {
      buf += d.toString();
      const lines = buf.split(/\r?\n/);
      buf = lines.pop() ?? "";
      for (const line of lines) if (line.trim()) console.log(`${tag} ${line}`);
    });
  };
  pipe(p.stdout);
  pipe(p.stderr);
  p.on("exit", (code) => {
    console.log(`${tag} exited with code ${code}`);
    shutdown(code ?? 0);
  });
  procs.push(p);
}

let stopping = false;
function shutdown(code) {
  if (stopping) return;
  stopping = true;
  for (const p of procs) if (!p.killed) p.kill();
  setTimeout(() => process.exit(code), 300);
}
process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));

if (singlePort) {
  log("building the web app");
  run("npm", ["run", "build"], { cwd: frontend });
  start("api", magenta, venvPython, ["-m", "uvicorn", "app.main:app", "--port", "8000"], backend);
} else {
  start("api", magenta, venvPython, ["-m", "uvicorn", "app.main:app", "--port", "8000", "--reload"], backend);
  start("web", cyan, "npm", ["run", "dev"], frontend);
}

setTimeout(() => {
  if (singlePort) {
    console.log(
      `\n${bold("JodiDar AI is starting (single port)")}\n` +
        `  App   ${cyan("http://localhost:8000")}\n` +
        `  Demo  ${cyan("http://localhost:8000/demo/compare")}\n` +
        dim("  Press Ctrl+C to stop.\n"),
    );
    return;
  }
  console.log(
    `\n${bold("JodiDar AI is starting")}\n` +
      `  App   ${cyan("http://localhost:5173")}\n` +
      `  Demo  ${cyan("http://localhost:5173/demo/compare")}\n` +
      `  API   ${magenta("http://localhost:8000/api/health")}\n` +
      dim("  Press Ctrl+C to stop.\n"),
  );
}, 2500);
