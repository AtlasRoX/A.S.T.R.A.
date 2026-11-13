// Starts ASTRA Core (Python, :8000) and the Next.js UI (:3000) together.
import { spawn } from 'node:child_process';
import { watch } from 'node:fs';
import { fileURLToPath } from 'node:url';

const isWin = process.platform === 'win32';
// `--prod`: the fast way to use the app (run `npm run build` first). No hot reload: optimized pages and the production
// React build, instead of compiling each page on first visit.
const prod = process.argv.includes('--prod');

// The engine is restarted by this script, not by `uvicorn --reload`. On Windows uvicorn's reloader stops its worker
// with CTRL_C_EVENT, which only reaches processes sharing its console; with the engine in its own hidden console (so a
// Ctrl+C there cannot stop this script and the web server) the worker never receives it and every reload hangs on
// "Reloading...". Killing and respawning the process tree works on every platform.
// `own`: the engine gets its own hidden console on Windows, so console signals for it never reach this script.
const engineArgs = ['run', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000'];
const procs = [
  { name: 'core', color: 36, cmd: 'uv', args: engineArgs, cwd: 'engine', own: true, watchDir: prod ? null : 'engine/app' },
  { name: 'web ', color: 35, cmd: 'pnpm', args: [prod ? 'start' : 'dev'], cwd: 'web' },
];

const tagOf = (p) => `\x1b[${p.color}m[${p.name}]\x1b[0m `;

function pipe(stream, out, tag) {
  let buf = '';
  stream.on('data', (d) => {
    buf += d.toString();
    const lines = buf.split(/\r?\n/);
    buf = lines.pop() ?? '';
    for (const l of lines) out.write(tag + l + '\n');
  });
}

function killTree(child) {
  if (child.exitCode !== null) return;
  if (isWin) spawn('taskkill', ['/pid', String(child.pid), '/T', '/F']);
  else child.kill('SIGTERM');
}

function start(p) {
  const cwd = new URL(`../${p.cwd}/`, import.meta.url);
  const child = isWin
    ? spawn([p.cmd, ...p.args].join(' '), { cwd, shell: true, env: process.env, detached: Boolean(p.own), windowsHide: true })
    : spawn(p.cmd, p.args, { cwd, env: process.env });
  const tag = tagOf(p);
  pipe(child.stdout, process.stdout, tag);
  pipe(child.stderr, process.stderr, tag);
  child.on('exit', (code) => {
    if (p.restarting || stopping) return;
    if (p.watchDir) {
      // A crash (say, a syntax error mid-edit) should not take the UI down: wait for the next change instead.
      process.stdout.write(`${tag}stopped (code ${code}); fix the error and save, and it restarts\n`);
      return;
    }
    process.stdout.write(`${tag}exited with code ${code}\n`);
    shutdown();
  });
  p.child = child;
  return child;
}

function restart(p, why) {
  const tag = tagOf(p);
  process.stdout.write(`${tag}${why}, restarting\n`);
  const old = p.child;
  if (!old || old.exitCode !== null) {
    start(p);
    return;
  }
  p.restarting = true;
  old.once('exit', () => {
    p.restarting = false;
    // Give the OS a moment to release the port before the new process binds it.
    setTimeout(() => start(p), 300);
  });
  killTree(old);
}

for (const p of procs) {
  start(p);
  if (p.watchDir) {
    let timer = null;
    let changed = '';
    const dir = fileURLToPath(new URL(`../${p.watchDir}/`, import.meta.url));
    watch(dir, { recursive: true }, (_event, file) => {
      if (!file || !String(file).endsWith('.py')) return;
      changed = String(file);
      clearTimeout(timer);
      timer = setTimeout(() => restart(p, `change in ${changed}`), 400);
    });
  }
}

let stopping = false;
function shutdown() {
  if (stopping) return;
  stopping = true;
  for (const p of procs) if (p.child) killTree(p.child);
  setTimeout(() => process.exit(0), 300);
}
process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);
// Closing the terminal window (Windows sends SIGHUP): stop the engine too, it runs in its own console.
process.on('SIGHUP', shutdown);
console.log(`
  ASTRA starting…  UI → http://localhost:${process.env.PORT ?? 3000}   Core API → http://127.0.0.1:8000/docs
`);
