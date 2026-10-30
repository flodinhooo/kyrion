// Host operator entry point for the existing bounded recovery helper.
import {spawn, execFile} from 'node:child_process';
import {openSync, closeSync} from 'node:fs';
import {readFile, mkdir} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {promisify} from 'node:util';
import {serviceReady, inspectService, waitUntilReady, startDatabase} from './dev-readiness.mjs';
import {commandSucceeded} from './dev-command.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const state = path.join(root, '.run/dev-recovery');
const execute = promisify(execFile);
const action = process.argv[2] ?? 'status';
const services = [
  {id: 'core', port: 8080}, {id: 'ai', port: 8000},
  {id: 'ollama', port: 11434}, {id: 'stt', port: 8040}, {id: 'tts', port: 8020},
];

async function webReady() {
  try {
    const response = await fetch('http://127.0.0.1:3000/recovery', {
      signal: AbortSignal.timeout(5000), redirect: 'manual',
    });
    return response.status === 200;
  } catch { return false; }
}

async function status() {
  const rows = await Promise.all(services.map(async (service) => {
    const probe = await inspectService(service);
    return {service: service.id, port: service.port, ready: probe.ready, code: probe.code, latencyMs: probe.latencyMs};
  }));
  rows.unshift({service: 'web', port: 3000, ready: await webReady()});
  let databaseReady = false;
  try {
    databaseReady = await commandSucceeded('docker.exe', ['exec', 'kyrion-postgres', 'sh', '-c',
      'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -Atqc "SELECT 1"'], {cwd: root});
  } catch { /* report database failure alongside all other services */ }
  rows.unshift({service: 'postgresql', port: 5432, ready: databaseReady});
  console.table(rows);
  return rows.every((row) => row.ready);
}

async function helper(method = 'GET', body) {
  const key = (await readFile(path.join(state, 'operator.key'), 'utf8')).trim();
  const response = await fetch('http://127.0.0.1:17654/', {
    method, headers: {Authorization: `Bearer ${key}`, 'Content-Type': 'application/json'},
    ...(body ? {body: JSON.stringify(body)} : {}), signal: AbortSignal.timeout(5000),
  });
  if (!response.ok) throw new Error(`RECOVERY_HTTP_${response.status}`);
  return response.json();
}

async function start(recoveryAction = 'start', target) {
  if (process.platform !== 'win32') throw new Error('WINDOWS_DEVELOPMENT_ONLY');
  await execute(process.execPath, [path.join(root, 'infrastructure/ensure-dev-recovery.mjs')],
    {cwd: root, windowsHide: true, timeout: 15000});
  // Start Web independently: the operator surface stays usable during recovery.
  if (!await webReady()) {
    await mkdir(state, {recursive: true});
    const output = openSync(path.join(state, 'web.log'), 'a');
    let child;
    try {
      child = spawn(process.execPath, [path.join(root, 'apps/web/node_modules/next/dist/bin/next'),
        'dev', '--hostname', '127.0.0.1', '--port', '3000'], {
        cwd: path.join(root, 'apps/web'), detached: true, windowsHide: true,
        stdio: ['ignore', output, output],
      });
    } finally { closeSync(output); }
    let failed = false;
    child.once('error', () => { failed = true; });
    child.unref();
    if (!await waitUntilReady(webReady, {
      timeoutMs: 90000, alive: () => !failed && child.exitCode === null,
    })) console.error('WEB_NOT_READY: inspect .run/dev-recovery/web.log');
  }
  let job = await helper();
  if (target && job.helperVersion !== '2026-10-30-scoped-v5') {
    throw new Error('HELPER_UPGRADE_REQUIRED: scoped restart needs the updated helper on its next safe launch.');
  }
  if (target && job.state === 'running') throw new Error('RECOVERY_BUSY');
  if (job.state !== 'running') job = await helper('POST', {action: recoveryAction, ...(target ? {service: target} : {})});
  console.log(`Recovery ${job.correlationId}; logs: .run/dev-recovery/`);
  let reported = 0;
  const completed = await waitUntilReady(async () => {
    job = await helper();
    for (const result of job.results.slice(reported)) console.log(`${result.id}: ${result.result}${result.code ? ` (${result.code})` : ''}`);
    reported = job.results.length;
    return job.state !== 'running';
  }, {timeoutMs: 2_100_000, intervalMs: 2000});
  const healthy = await status();
  if (!completed || job.state !== 'completed' || !healthy) process.exitCode = 1;
}

async function restartDatabase() {
  const core = {id: 'core', port: 8080};
  const coreWasReady = await serviceReady(core);
  // Explicit operator action, preserving this existing container and its data.
  console.log('Restarting only kyrion-postgres with a 120-second graceful stop.');
  const stopped = await commandSucceeded('docker.exe', ['stop', '--time', '120', 'kyrion-postgres'],
    {cwd: root, timeoutMs: 135000});
  // Always attempt recovery, even if the client timed out during stop.
  const ready = await startDatabase(async (file, args, timeoutMs) => {
    if (!await commandSucceeded(file, args, {cwd: root, timeoutMs})) throw new Error('DATABASE_COMMAND_FAILED');
  });
  if (!stopped || !ready) throw new Error('DATABASE_RESTART_INCOMPLETE: inspect database logs and readiness.');
  if (coreWasReady && !await waitUntilReady(() => serviceReady(core), {
    timeoutMs: 30000, intervalMs: 500,
  })) throw new Error('CORE_RECONNECT_FAILED: SQL is ready but Core has not recovered.');
  if (!await status()) process.exitCode = 1;
}

try {
  if (action === 'start') await start();
  else if (action === 'diagnose') {
    const result = await execute(process.execPath, [path.join(root, 'infrastructure/dev-diagnostics.mjs')],
      {cwd: root, windowsHide: true, timeout: 30000});
    console.log(result.stdout);
  }
  else if (action === 'restart' && process.argv[3] === '--confirm') await start('restart');
  else if (action === 'restart' && process.argv[4] === '--confirm'
    && ['core', 'ai', 'ollama'].includes(process.argv[3])) await start('restart', process.argv[3]);
  else if (action === 'restart' && process.argv[3] === 'postgres' && process.argv[4] === '--confirm') await restartDatabase();
  else if (action === 'status' || action === 'health') process.exitCode = await status() ? 0 : 1;
  else if (action === 'logs') {
    const id = process.argv[3];
    if (!['web', 'helper', ...services.map((service) => service.id)].includes(id)) {
      throw new Error('Usage: node infrastructure/dev-stack.mjs logs web|helper|core|ai|ollama|stt|tts');
    }
    const lines = (await readFile(path.join(state, `${id}.log`), 'utf8')).split(/\r?\n/);
    console.log(lines.slice(-80).join('\n'));
  } else throw new Error('Usage: node infrastructure/dev-stack.mjs start|status|health|logs [service]|restart [core|ai|ollama|postgres] --confirm');
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
