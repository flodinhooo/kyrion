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
  const [pathname, valid] = endpoints[service.id];
  try {
    const response = await fetcher(`http://127.0.0.1:${service.port}${pathname}`, {
      signal: AbortSignal.timeout(2000), redirect: 'error',
    });
    if (!response.ok) return false;
    const body = await response.json();
    return body !== null && typeof body === 'object' && valid(body);
  } catch { return false; }
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
