#!/usr/bin/env node
// One command to run DealMeet AI locally: installs what's missing on first run,
// then starts the API (FastAPI, :8000) and the web app (Vite, :5173) together.
// Works on macOS, Linux and Windows with only Node 22.12+ (or 20.19+) and Python 3.10 to 3.14.
import { spawn, spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, readFileSync, rmSync, writeFileSync } from "node:fs";
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

// Vite (the web dev server) needs Node 20.19+ or 22.12+; older versions crash after
// the install, so say so up front.
const [nodeMajor, nodeMinor] = process.versions.node.split(".").map(Number);
if (!((nodeMajor === 20 && nodeMinor >= 19) || (nodeMajor === 22 && nodeMinor >= 12) || nodeMajor > 22)) {
  console.error(`Node ${process.versions.node} is too old for the web app (it needs 20.19+ or 22.12+). Install Node 22 LTS from nodejs.org and run again.`);
  process.exit(1);
}

// The pinned API packages ship ready-made builds for Python 3.10 to 3.14 on Windows,
// macOS and Linux. Outside that range pip tries to compile numpy and friends from
// source, which fails without a C compiler.
const PY_RANGE = "3.10 to 3.14";
const PY_PROBE = "import sys; print([3, 10] <= list(sys.version_info[:2]) <= [3, 14])";
const PY_PREFERRED = ["3.13", "3.12", "3.14", "3.11", "3.10"];

function supportedPython(cmd, pre = []) {
  const r = spawnSync(cmd, [...pre, "-c", PY_PROBE], { encoding: "utf8" });
  return r.status === 0 && r.stdout.trim() === "True";
}

function findPython() {
  // Prefer a specific supported version over "newest installed": on Windows `py -3`
  // picks the newest Python, which may be too new for the pinned packages.
  const candidates = isWin
    ? [...PY_PREFERRED.map((v) => ["py", [`-${v}`]]), ["py", ["-3"]], ["python", []]]
    : [...PY_PREFERRED.map((v) => [`python${v}`, []]), ["python3", []], ["python", []]];
  for (const [cmd, pre] of candidates) if (supportedPython(cmd, pre)) return [cmd, pre];
  return null;
}

// npm is npm.cmd on Windows, which Node can only start through cmd.exe. Everything
// else (python.exe, py.exe) is started directly so paths with spaces stay intact.
const needsShell = (cmd) => isWin && (cmd === "npm" || cmd === "npx");

function run(cmd, args, opts = {}) {
  const r = spawnSync(cmd, args, { stdio: "inherit", shell: needsShell(cmd), ...opts });
  if (r.status !== 0) {
    if (r.error) console.error(r.error.message);
    console.error(`\n${magenta("jodidar")} command failed: ${cmd} ${args.join(" ")}`);
    process.exit(r.status ?? 1);
  }
}

/** Windows limits paths to 260 characters unless long paths are enabled; one installed file is deep. */
function warnLongPaths() {
  if (!isWin) return;
  const deepest = join(backend, ".venv", "Lib", "site-packages").length + 110;
  if (deepest < 255) return;
  const reg = spawnSync("reg", ["query", "HKLM\\SYSTEM\\CurrentControlSet\\Control\\FileSystem", "/v", "LongPathsEnabled"], {
    encoding: "utf8",
  });
  if (/LongPathsEnabled\s+REG_DWORD\s+0x1\b/i.test(reg.stdout ?? "")) return;
  log(
    "warning: this folder path is long, and Windows may refuse to install some packages.\n" +
      "  If the install fails, move the project to a shorter path (for example C:\\DealMeet-AI)\n" +
      "  or enable long paths: https://learn.microsoft.com/windows/win32/fileio/maximum-file-path-limitation",
  );
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
  if (existsSync(venvPython) && !supportedPython(venvPython)) {
    log(`the API environment uses a Python outside ${PY_RANGE}; rebuilding it`);
    rmSync(join(backend, ".venv"), { recursive: true, force: true });
    rmSync(stamp, { force: true });
  }
  if (!existsSync(venvPython)) {
    const py = findPython();
    if (!py) {
      console.error(`Python ${PY_RANGE} is required. Install Python 3.13 from python.org and run again.`);
      process.exit(1);
    }
    log("creating Python virtual environment (first run only)");
    run(py[0], [...py[1], "-m", "venv", join(backend, ".venv")]);
  }
  const want = hashFile(reqs);
  const have = existsSync(stamp) ? readFileSync(stamp, "utf8").trim() : "";
  if (want !== have) {
    log("installing API dependencies");
    warnLongPaths();
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

/** A value from the repo-root .env, if the file sets it. */
function dotenv(key) {
  const file = join(root, ".env");
  if (!existsSync(file)) return undefined;
  for (const line of readFileSync(file, "utf8").replace(/^\uFEFF/, "").split(/\r?\n/)) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)$/);
    if (m && m[1] === key) return m[2].trim().replace(/^["']|["']$/g, "") || undefined;
  }
  return undefined;
}

// The local runner starts the demo (seeded personas, demo sign-in, the Reset button) unless
// DEMO_MODE=0 is set in the environment or .env. The API itself defaults to demo mode off.
const DEMO_MODE = process.env.DEMO_MODE ?? dotenv("DEMO_MODE") ?? "1";
// A "Demo admin" persona for walking through the admin console. Local only: the API turns it
// off on a demo that resets itself (a shared URL) and outside demo mode.
const DEMO_ADMIN = process.env.DEMO_ADMIN ?? dotenv("DEMO_ADMIN") ?? "1";
// No MONGODB_URI: run on the in-memory database, said out loud (the API never falls back on its own).
const USE_MOCK_DB = process.env.USE_MOCK_DB ?? dotenv("USE_MOCK_DB") ?? (process.env.MONGODB_URI ?? dotenv("MONGODB_URI") ? "0" : "1");

const procs = [];
function start(name, color, cmd, args, cwd) {
  const p = spawn(cmd, args, { cwd, shell: needsShell(cmd), env: { ...process.env, DEMO_MODE, DEMO_ADMIN, USE_MOCK_DB, FORCE_COLOR: "1" } });
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

function stop(p) {
  if (p.exitCode !== null || p.signalCode !== null) return; // already gone
  if (isWin) {
    // kill() only ends the top process; /T also ends what it started (the uvicorn
    // reloader and worker, or npm and vite), so nothing keeps holding the port.
    spawnSync("taskkill", ["/pid", String(p.pid), "/T", "/F"], { stdio: "ignore" });
  } else {
    p.kill();
  }
}

let stopping = false;
function shutdown(code) {
  if (stopping) return;
  stopping = true;
  for (const p of procs) stop(p);
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
      `\n${bold("DealMeet AI is starting (single port)")}\n` +
        `  App   ${cyan("http://localhost:8000")}\n` +
        `  Demo  ${cyan("http://localhost:8000/login")}\n` +
        dim("  Press Ctrl+C to stop.\n"),
    );
    return;
  }
  console.log(
    `\n${bold("DealMeet AI is starting")}\n` +
      `  App   ${cyan("http://localhost:5173")}\n` +
      `  Demo  ${cyan("http://localhost:5173/login")}\n` +
      `  API   ${magenta("http://localhost:8000/api/health")}\n` +
      dim("  Press Ctrl+C to stop.\n"),
  );
}, 2500);
