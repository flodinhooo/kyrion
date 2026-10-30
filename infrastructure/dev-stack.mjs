// Host operator entry point for the existing bounded recovery helper.
import {spawn, execFile} from 'node:child_process';
import {openSync, closeSync} from 'node:fs';
import {readFile, mkdir} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {promisify} from 'node:util';
import {serviceReady, waitUntilReady} from './dev-readiness.mjs';
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
  const rows = await Promise.all(services.map(async (service) => ({
    service: service.id, port: service.port, ready: await serviceReady(service),
  })));
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

async function start(recoveryAction = 'start') {
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
  if (job.state !== 'running') job = await helper('POST', {action: recoveryAction});
  console.log(`Recovery ${job.correlationId}; logs: .run/dev-recovery/`);
  let reported = 0;
  const completed = await waitUntilReady(async () => {
    job = await helper();
    for (const result of job.results.slice(reported)) console.log(`${result.id}: ${result.result}`);
    reported = job.results.length;
    return job.state !== 'running';
  }, {timeoutMs: 2_100_000, intervalMs: 2000});
  const healthy = await status();
  if (!completed || job.state !== 'completed' || !healthy) process.exitCode = 1;
}

try {
  if (action === 'start') await start();
  else if (action === 'restart' && process.argv[3] === '--confirm') await start('restart');
  else if (action === 'status' || action === 'health') process.exitCode = await status() ? 0 : 1;
  else if (action === 'logs') {
    const id = process.argv[3];
    if (!['web', 'helper', ...services.map((service) => service.id)].includes(id)) {
      throw new Error('Usage: node infrastructure/dev-stack.mjs logs web|helper|core|ai|ollama|stt|tts');
    }
    const lines = (await readFile(path.join(state, `${id}.log`), 'utf8')).split(/\r?\n/);
    console.log(lines.slice(-80).join('\n'));
  } else throw new Error('Usage: node infrastructure/dev-stack.mjs start|status|health|logs [service]|restart --confirm');
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
