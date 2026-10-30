// Explicit local operator tool. Never import this module into Web.
import {createServer} from 'node:http';
import {randomBytes, randomUUID} from 'node:crypto';
import {mkdir, readFile, writeFile, appendFile, copyFile} from 'node:fs/promises';
import {openSync, closeSync} from 'node:fs';
import {spawn} from 'node:child_process';
import {createConnection} from 'node:net';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {homedir} from 'node:os';
import {authorisedKey, validAction, canRestartManagedProcess} from './dev-recovery-policy.mjs';
import {serviceReady, startDatabase, waitUntilReady} from './dev-readiness.mjs';

if (process.platform !== 'win32') throw new Error('Windows development helper only');
const root = fileURLToPath(new URL('../', import.meta.url));
const stateDir = path.join(root, '.run', 'dev-recovery');
await mkdir(stateDir, {recursive: true});
await command('icacls.exe', [stateDir, '/inheritance:r', '/grant:r', `${process.env.USERDOMAIN}\\${process.env.USERNAME}:(OI)(CI)F`]);
const keyPath = path.join(stateDir, 'operator.key');
try {
  await writeFile(keyPath, randomBytes(32).toString('hex'), {flag: 'wx', mode: 0o600});
} catch (error) {
  if (error.code !== 'EEXIST') throw error;
}
await command('icacls.exe', [keyPath, '/inheritance:r', '/grant:r', `${process.env.USERDOMAIN}\\${process.env.USERNAME}:F`]);
const key = (await readFile(keyPath, 'utf8')).trim();
if (!/^[a-f0-9]{64}$/.test(key)) throw new Error('Invalid operator key file');
let settings = {};
try {
  settings = JSON.parse(await readFile(path.join(stateDir, 'settings.json'), 'utf8'));
} catch (error) {
  if (error.code !== 'ENOENT') throw error;
}
if (!settings || typeof settings !== 'object' || Array.isArray(settings)
  || Object.keys(settings).some((name) => !['coreJar', 'piHost'].includes(name))
  || (settings.coreJar !== undefined && typeof settings.coreJar !== 'string')
  || (settings.piHost !== undefined && typeof settings.piHost !== 'string')) throw new Error('Invalid local recovery settings');
const piHost = process.env.KYRION_RECOVERY_PI_HOST ?? settings.piHost;
if (piHost && !/^[a-zA-Z0-9.-]+$/.test(piHost)) throw new Error('Invalid configured Pi host');
const coreArtifact = path.resolve(process.env.KYRION_RECOVERY_CORE_JAR ?? settings.coreJar ?? path.join(root, 'services/core/build/libs/kyrion-core-0.1.0-SNAPSHOT.jar'));
const frozenCoreArtifact = path.join(stateDir, 'core-runtime.jar');
const managed = new Map();
let job = {state: 'idle', correlationId: null, results: []};
let lastAttempt = 0;
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function listening(port) {
  return new Promise((resolve) => {
    const socket = createConnection({host: '127.0.0.1', port});
    socket.setTimeout(600);
    socket.once('connect', () => {
      socket.destroy();
      resolve(true);
    });
    socket.once('error', () => {
      socket.destroy();
      resolve(false);
    });
    socket.once('timeout', () => {
      socket.destroy();
      resolve(false);
    });
  });
}

function command(file, args, timeout = 30_000) {
  return new Promise((resolve, reject) => {
    const child = spawn(file, args, {cwd: root, windowsHide: true, stdio: 'ignore', timeout});
    child.once('error', reject);
    child.once('exit', (code) => code === 0 ? resolve() : reject(new Error('COMMAND_FAILED')));
  });
}

const services = [
  {id: 'ollama', port: 11434, file: 'E:\\Ollama\\App\\ollama.exe', args: ['serve'], cwd: root},
  {
    id: 'core',
    port: 8080,
    file: process.env.JAVA_HOME ? path.join(process.env.JAVA_HOME, 'bin/java.exe') : 'java.exe',
    args: ['-jar', frozenCoreArtifact],
    cwd: path.join(root, 'services/core')
  },
  {
    id: 'ai',
    port: 8000,
    file: path.join(root, 'services/ai/.venv/Scripts/python.exe'),
    args: ['-m', 'uvicorn', 'kyrion_ai.app:app', '--host', '127.0.0.1', '--port', '8000'],
    cwd: path.join(root, 'services/ai')
  },
  {
    id: 'stt',
    port: 8040,
    file: 'wsl.exe',
    args: ['-d', 'Kyrion-Voice-Training', '--', '/training/tools/nemo-speech-install/bin/nemo-speech', 'serve', '--host', '0.0.0.0', '--port', '8040', '--asr-model', '/training/models/parakeet-tdt-0.6b-v3/parakeet-tdt-0.6b-v3.q8_0.gguf', '--device', 'cpu', '--no-ui', '--access-log'],
    cwd: root
  },
  {
    id: 'tts',
    port: 8020,
    file: 'wsl.exe',
    args: ['-d', 'Kyrion-Voice-Training', '--', '/training/chatterbox-venv/bin/python', '/mnt/e/dev/Kyrion/kyrion/services/ai/runtime/chatterbox_tts_server.py', '--host', '0.0.0.0', '--port', '8020'],
    cwd: root
  },
];

async function audit(event) {
  await appendFile(path.join(stateDir, 'audit.jsonl'), JSON.stringify({
    at: new Date().toISOString(),
    actor: 'local-operator', ...event
  }) + '\n');
}

async function run(action, correlationId) {
  try {
    await audit({event: 'requested', action, correlationId});
    // Database start is idempotent; never restart a database automatically.
    let databaseReady = false;
    try {
      databaseReady = await startDatabase(command);
      if (!databaseReady) throw new Error('DATABASE_NOT_READY');
      job.results.push({id: 'postgresql', result: 'started'});
    } catch {
      job.results.push({id: 'postgresql', result: 'failed'});
    }
    for (const service of services) {
      try {
        if (service.id === 'core' && !databaseReady) {
          job.results.push({id: service.id, result: 'failed'});
          continue;
        }
        const child = managed.get(service.id);
        if (canRestartManagedProcess(action, service.file, child)) {
          await audit({
            event: 'service_stop_requested', correlationId, service: service.id,
            method: 'windows_process_tree'
          });
          await command('taskkill.exe', ['/PID', String(child.pid), '/T', '/F']);
          managed.delete(service.id);
          for (let i = 0; i < 20 && await listening(service.port); i++) await sleep(500);
        }
        if (await listening(service.port)) {
          const healthy = await waitUntilReady(() => serviceReady(service), {
            timeoutMs: service.id === 'tts' ? 900_000 : 180_000,
          });
          job.results.push({id: service.id, result: healthy ? 'already_running' : 'failed'});
          continue;
        }
        const pending = managed.get(service.id);
        if (pending && pending.exitCode === null && !pending.killed) {
          // A previous request may have timed out during model initialization.
          // Reuse that process; never load a second copy or terminate WSL.
          const healthy = await waitUntilReady(() => serviceReady(service), {
            timeoutMs: service.id === 'tts' ? 900_000 : 180_000,
            alive: () => pending.exitCode === null && !pending.killed,
          });
          job.results.push({id: service.id, result: healthy ? 'already_running' : 'failed'});
          continue;
        }
        if (service.id === 'core') await copyFile(coreArtifact, frozenCoreArtifact);
        const output = openSync(path.join(stateDir, `${service.id}.log`), 'a');
        let launched;
        try {
          launched = spawn(service.file, service.args, {
            cwd: service.cwd,
            windowsHide: true,
            stdio: ['ignore', output, output]
          });
        } finally {
          closeSync(output);
        }
        managed.set(service.id, launched);
        let failed = false;
        launched.once('error', () => {
          failed = true;
        });
        const ready = await waitUntilReady(() => serviceReady(service), {
          timeoutMs: service.id === 'tts' ? 900_000 : 180_000,
          alive: () => !failed && launched.exitCode === null,
        });
        job.results.push({id: service.id, result: ready ? 'started' : 'failed'});
      } catch {
        job.results.push({id: service.id, result: 'failed'});
      }
    }
    if (piHost) {
      for (const [id, unit] of [['spotify-receiver', 'kyrion-spotify-receiver.service'], ['voice-satellite', 'kyrion-voice-satellite.service'], ['media-player', 'kyrion-media-player.service']]) {
        try {
          await command('ssh.exe', ['-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5', '-o', 'StrictHostKeyChecking=yes', '-o', 'HostKeyAlias=kyrion-node.local', '-i', path.join(homedir(), '.ssh/kyrion_node_ed25519'), `flodinho@${piHost}`, `systemctl --user ${action} ${unit} && systemctl --user is-active --quiet ${unit}`], 20_000);
          job.results.push({id, result: 'started'});
        } catch {
          job.results.push({id, result: 'failed'});
        }
      }
    }
    job.state = job.results.some((item) => item.result === 'failed') ? 'failed' : 'completed';
    await audit({event: job.state, action, correlationId, results: job.results});
  } catch {
    job.state = 'failed';
  }
}

const server = createServer(async (request, response) => {
  const reply = (status, body) => {
    response.writeHead(status, {'Content-Type': 'application/json', 'Cache-Control': 'no-store'});
    response.end(JSON.stringify(body));
  };
  if (!authorisedKey(request.headers.authorization?.replace(/^Bearer /, ''), key)) return reply(401, {code: 'UNAUTHORISED'});
  if (request.url !== '/') return reply(404, {code: 'NOT_FOUND'});
  if (request.method === 'GET') return reply(200, {...job, helperVersion: '2026-10-30-readiness-v4'});
  if (request.method !== 'POST') return reply(405, {code: 'METHOD_NOT_ALLOWED'});
  if (job.state === 'running' || Date.now() - lastAttempt < 5000) return reply(409, {code: 'RECOVERY_BUSY'});
  let raw = '';
  try {
    for await (const chunk of request) {
      raw += chunk;
      if (raw.length > 256) return reply(413, {code: 'INVALID_REQUEST'});
    }
    const value = JSON.parse(raw);
    if (!validAction(value)) return reply(400, {code: 'INVALID_REQUEST'});
    lastAttempt = Date.now();
    job = {state: 'running', correlationId: randomUUID(), results: []};
    void run(value.action, job.correlationId);
    reply(202, job);
  } catch {
    reply(400, {code: 'INVALID_REQUEST'});
  }
});
server.requestTimeout = 5000;
server.listen(17654, '127.0.0.1', () => console.log(`Local recovery ready. Operator key: ${keyPath}`));
