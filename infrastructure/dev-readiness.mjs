// Readiness, rather than an open socket, gates dependent development services.
export async function waitUntilReady(probe, {
  timeoutMs, intervalMs = 1000, alive = () => true,
  now = () => performance.now(), sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
}) {
  const deadline = now() + timeoutMs;
  while (alive()) {
    try { if (await probe()) return true; } catch { /* retry bounded startup failures */ }
    const remaining = deadline - now();
    if (remaining <= 0) return false;
    await sleep(Math.min(intervalMs, remaining));
  }
  return false;
}

const endpoints = {
  core: ['/actuator/health', (body) => body.status === 'UP'],
  ai: ['/health', (body) => body.status === 'ok'],
  ollama: ['/api/version', (body) => typeof body.version === 'string' && body.version.length > 0],
  stt: ['/health', (body) => body.status === 'ok'],
  tts: ['/health', (body) => body.status === 'ready'],
};

export async function serviceReady(service, fetcher = fetch) {
  return (await inspectService(service, fetcher)).ready;
}

export async function inspectService(service, fetcher = fetch) {
  const started = performance.now();
  const result = (ready, code) => ({ready, code, latencyMs: Math.round(performance.now() - started)});
  const endpoint = endpoints[service.id];
  if (!endpoint) return result(false, 'UNSUPPORTED_SERVICE');
  const [pathname, valid] = endpoint;
  try {
    const response = await fetcher(`http://127.0.0.1:${service.port}${pathname}`, {
      signal: AbortSignal.timeout(2000), redirect: 'error',
    });
    if (!response.ok) return result(false, `HTTP_${response.status}`);
    const body = await response.json();
    if (body !== null && typeof body === 'object' && valid(body)) return result(true, 'READY');
    return result(false, body && typeof body.status === 'string' ? 'NOT_READY' : 'INVALID_RESPONSE');
  } catch (error) {
    return result(false, ['AbortError', 'TimeoutError'].includes(error?.name) ? 'PROBE_TIMEOUT'
      : error instanceof SyntaxError ? 'INVALID_RESPONSE' : 'UNREACHABLE');
  }
}

export async function startDatabase(command, options = {}) {
  // Compose --wait exits early when crash recovery exceeds healthcheck retries.
  // Never recreate an existing container or change its data/configuration here.
  await command('docker.exe', ['compose', '-f', 'infrastructure/compose.yml', 'up', '-d', '--no-recreate', 'postgres'], 180_000);
  return waitUntilReady(async () => {
    await command('docker.exe', ['exec', 'kyrion-postgres', 'sh', '-c',
      'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -Atqc "SELECT 1"'], 5000);
    return true;
  }, {timeoutMs: 600_000, ...options});
}
