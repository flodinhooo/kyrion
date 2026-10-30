// Demo checks; optional mutations use only explicitly marked disposable objects.
import {createRequire} from 'node:module';
import {fileURLToPath, pathToFileURL} from 'node:url';
import path from 'node:path';
import {serviceReady, waitUntilReady} from './dev-readiness.mjs';
import {localCalendarSmoke} from './demo-calendar.mjs';
import {googleCalendarSmoke} from './demo-google.mjs';

export const demoPages = ['/', '/home', '/devices', '/calendar', '/plugins', '/lounge',
  '/chat', '/settings/services', '/users', '/roles'];

export function apiSummary(route, http, body) {
  const result = {check: route, passed: http >= 200 && http < 300, http};
  if (typeof body?.code === 'string' && /^[A-Z_]{1,80}$/.test(body.code)) result.code = body.code;
  if (Array.isArray(body)) result.count = body.length;
  if (Array.isArray(body?.items)) result.count = body.items.length;
  for (const field of ['connected', 'configured', 'reauthorizationRequired']) {
    if (typeof body?.[field] === 'boolean') result[field] = body[field];
  }
  if (['healthy', 'degraded', 'offline', 'unknown'].includes(body?.status)) result.state = body.status;
  if (result.connected === false || result.configured === false || result.reauthorizationRequired
    || ['degraded', 'offline', 'unknown'].includes(result.state)) result.passed = false;
  return result;
}

export async function waitForHaRefresh(before, readStatus, options = {}) {
  const baseline = Date.parse(before.lastSuccessAt);
  if (!Number.isFinite(baseline)) return false;
  // Manual sync resets the 30s throttle; one scheduled tick can be skipped.
  return waitUntilReady(async () => {
    const after = await readStatus();
    return after.status === 'healthy' && Date.parse(after.lastSuccessAt) > baseline;
  }, {timeoutMs: 75000, intervalMs: 5000, ...options});
}

export async function publicSmoke(fetcher = fetch) {
  const rows = await Promise.all([
    {id: 'core', port: 8080}, {id: 'ai', port: 8000}, {id: 'ollama', port: 11434},
    {id: 'stt', port: 8040}, {id: 'tts', port: 8020},
  ].map(async (service) => ({check: service.id, passed: await serviceReady(service, fetcher)})));
  for (const route of ['/login', '/recovery']) {
    try {
      const response = await fetcher(`http://localhost:3000${route}`, {
        signal: AbortSignal.timeout(15000), redirect: 'manual',
      });
      rows.push({check: `web${route}`, passed: response.status === 200});
    } catch {
      rows.push({check: `web${route}`, passed: false});
    }
  }
  try {
    const response = await fetcher('http://localhost:3000/api/devices', {
      signal: AbortSignal.timeout(10000), redirect: 'manual',
    });
    rows.push({check: 'unauthenticated-device-access-denied', passed: response.status === 401});
  } catch {
    rows.push({check: 'unauthenticated-device-access-denied', passed: false});
  }
  return rows;
}

async function browserSmoke() {
  // Reuse the repository's existing Playwright installation; add no dependency.
  const require = createRequire(new URL('../apps/website/package.json', import.meta.url));
  const {chromium} = require('@playwright/test');
  // Only this workflow's dedicated profile is used, never unrelated credential caches.
  const profile = fileURLToPath(new URL('../.run/dev-recovery/demo-browser', import.meta.url));
  const context = await chromium.launchPersistentContext(profile, {
    headless: !process.argv.includes('--interactive'), baseURL: 'http://localhost:3000',
  });
  const page = await context.newPage();
  const rows = [];
  try {
    await page.goto('/login');
    console.log(process.argv.includes('--interactive')
      ? 'Sign in locally if needed. Credentials stay in this workflow\'s test browser.'
      : 'Checking this workflow\'s dedicated authenticated test profile.');
    const deadline = Date.now() + (process.argv.includes('--interactive') ? 300000 : 1000);
    let authenticated = false;
    while (Date.now() < deadline) {
      const response = await context.request.get('/api/auth/me', {timeout: 10000});
      if (response.status() === 200) {
        authenticated = true;
        break;
      }
      await new Promise((resolve) => setTimeout(resolve, 2000));
    }
    if (!authenticated) return [{check: 'authenticated-browser', passed: false, code: 'LOGIN_REQUIRED'}];
    for (const route of demoPages) {
      let errors = 0;
      const onError = () => {
        errors++;
      };
      const onResponse = (response) => {
        if (response.url().startsWith('http://localhost:3000/') && response.status() >= 500) errors++;
      };
      page.on('pageerror', onError);
      page.on('response', onResponse);
      try {
        const response = await page.goto(route, {timeout: 30000, waitUntil: 'domcontentloaded'});
        await page.waitForTimeout(1500);
        const actualPath = new URL(page.url()).pathname;
        rows.push({
          check: `page${route}`, passed: response?.status() === 200 && actualPath === route
            && errors === 0, errors, redirected: actualPath !== route
        });
      } catch {
        rows.push({check: `page${route}`, passed: false, code: 'NAVIGATION_FAILED'});
      } finally {
        page.off('pageerror', onError);
        page.off('response', onResponse);
      }
    }
    for (const route of ['/api/home/rooms', '/api/devices', '/api/integrations/google',
      '/api/integrations/google/calendar/calendars', '/api/integrations/home-assistant',
      '/api/integrations/spotify', '/api/integrations/spotify/devices', '/api/gateways']) {
      try {
        const response = await context.request.get(route, {timeout: 30000});
        const body = await response.json();
        rows.push(apiSummary(route, response.status(), body));
      } catch {
        rows.push({check: route, passed: false, code: 'REQUEST_FAILED'});
      }
    }
    if (process.argv.includes('--refresh-ha')) {
      const csrf = (await context.cookies()).find((cookie) => cookie.name === 'kyrion_csrf')?.value;
      if (!csrf) rows.push({check: 'ha-manual-refresh', passed: false, code: 'CSRF_REQUIRED'});
      else {
        const response = await context.request.post('/api/integrations/home-assistant/sync', {
          headers: {'x-kyrion-csrf': csrf}, timeout: 30000,
        });
        const body = await response.json();
        rows.push({
          check: 'ha-manual-refresh', passed: response.ok() && !body.reason,
          http: response.status(), imported: Number.isInteger(body.imported) ? body.imported : null
        });
        const before = await (await context.request.get('/api/integrations/home-assistant')).json();
        console.log('HA_AUTOMATIC_REFRESH: observing scheduler ticks without on-demand device reads.');
        rows.push({
          check: 'ha-automatic-refresh', passed: await waitForHaRefresh(before,
            async () => (await context.request.get('/api/integrations/home-assistant', {timeout: 10000})).json())
        });
      }
    }
    if (process.argv.includes('--google-calendar')) {
      const csrf = (await context.cookies()).find((cookie) => cookie.name === 'kyrion_csrf')?.value;
      if (csrf) rows.push(...await googleCalendarSmoke(context.request, csrf));
      else rows.push({check: 'google-calendar', passed: false, code: 'CSRF_REQUIRED'});
    }
    if (process.argv.includes('--local-calendar')) {
      const csrf = (await context.cookies()).find((cookie) => cookie.name === 'kyrion_csrf')?.value;
      if (csrf) rows.push(...await localCalendarSmoke(context.request, csrf));
      else rows.push({check: 'local-calendar', passed: false, code: 'CSRF_REQUIRED'});
    }
    return rows;
  } finally {
    await context.close();
  }
}

if (process.argv[1] && pathToFileURL(path.resolve(process.argv[1])).href === import.meta.url) {
  try {
    const rows = await publicSmoke();
    const browser = process.argv.includes('--interactive') || process.argv.includes('--browser');
    if (browser) rows.push(...await browserSmoke());
    console.table(rows);
    if (!browser) console.log('AUTHENTICATED_UI_AND_HARDWARE: not verified (use --interactive for UI).');
    process.exitCode = rows.every((row) => row.passed) ? 0 : 1;
  } catch {
    console.error('DEMO_SMOKE_FAILED: check service readiness and the existing Playwright installation.');
    process.exitCode = 1;
  }
}
