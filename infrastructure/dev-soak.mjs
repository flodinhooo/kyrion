import {writeFile, mkdir} from 'node:fs/promises';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {inspectService} from './dev-readiness.mjs';
import {commandSucceeded} from './dev-command.mjs';
import {collectDiagnostics} from './dev-diagnostics.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));

async function snapshot() {
  const rows = await Promise.all([{id: 'core', port: 8080}, {id: 'ai', port: 8000},
    {id: 'ollama', port: 11434}, {id: 'stt', port: 8040}, {id: 'tts', port: 8020}]
    .map(async (service) => ({id: service.id, ...await inspectService(service)})));
  let web = false;
  try {
    web = (await fetch('http://localhost:3000/recovery', {signal: AbortSignal.timeout(5000)})).ok;
  } catch { /* retain an unavailable sample */
  }
  rows.push({id: 'web', ready: web}, {
    id: 'postgres', ready: await commandSucceeded('docker.exe',
      ['exec', 'kyrion-postgres', 'sh', '-c',
        'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -Atqc "SELECT 1"'], {cwd: root})
  });
  return rows;
}

export async function observeServices({
                                        durationMs = 300000,
                                        intervalMs = 10000,
                                        probe = snapshot,
                                        now = () => performance.now(),
                                        sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
                                        onSample = () => {
                                        }
                                      } = {}) {
  const started = now();
  const result = {samples: 0, failureCount: 0, failures: [], elapsedMs: 0};
  while (true) {
    const rows = await probe();
    result.samples++;
    for (const row of rows) if (!row.ready) {
      result.failureCount++;
      if (result.failures.length < 100) result.failures.push({
        service: row.id, offsetMs: Math.round(now() - started),
        ...(row.code ? {code: row.code, latencyMs: row.latencyMs} : {})
      });
    }
    result.elapsedMs = Math.round(now() - started);
    onSample(result.samples, result.failureCount);
    const remaining = durationMs - (now() - started);
    if (remaining <= 0) return result;
    await sleep(Math.min(intervalMs, remaining));
  }
}

if (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url) {
  const minutes = Number(process.argv[2] ?? 5);
  if (!Number.isFinite(minutes) || minutes < 1 || minutes > 120) {
    console.error('Usage: node infrastructure/dev-soak.mjs [minutes: 1..120]');
    process.exitCode = 1;
  } else {
    const before = await collectDiagnostics();
    console.log(`Observing seven services for ${minutes} minutes; no automatic restart or synthesis.`);
    const result = await observeServices({
      durationMs: minutes * 60000,
      onSample: (samples, failures) => {
        if (samples === 1 || samples % 6 === 0) console.log(`samples=${samples} failedChecks=${failures}`);
      }
    });
    const after = await collectDiagnostics();
    const sameBoot = before.wsl?.bootId && before.wsl.bootId === after.wsl?.bootId;
    const sameContainerStart = before.containers[0]?.startedAt
      && before.containers[0].startedAt === after.containers[0]?.startedAt;
    const report = {
      ...result, startedAt: before.at, endedAt: after.at,
      sameWslBoot: Boolean(sameBoot), sameDatabaseStart: Boolean(sameContainerStart),
      diagnosticsComplete: before.unavailable.length === 0 && after.unavailable.length === 0
    };
    const directory = new URL('../.run/dev-recovery/soak/', import.meta.url);
    await mkdir(directory, {recursive: true});
    await writeFile(new URL(`${Date.now()}.json`, directory), JSON.stringify(report, null, 2) + '\n', {mode: 0o600});
    console.log(JSON.stringify(report, null, 2));
    if (result.failureCount || !sameBoot || !sameContainerStart || !report.diagnosticsComplete) process.exitCode = 1;
  }
}
