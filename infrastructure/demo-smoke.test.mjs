import test from 'node:test';
import assert from 'node:assert/strict';
import {apiSummary, publicSmoke, waitForHaRefresh} from './demo-smoke.mjs';

test('HA manual-sync throttle can skip a scheduler tick without implying a broken scheduler', async () => {
  let time = 0;
  const before = {lastSuccessAt: '2026-10-30T18:00:00Z'};
  assert.equal(await waitForHaRefresh(before, async () => ({
    status: 'healthy',
    lastSuccessAt: time < 59000 ? before.lastSuccessAt : '2026-10-30T18:01:00Z'
  }), {
    now: () => time, sleep: async (ms) => {
      time += ms;
    },
  }), true);
  assert.equal(time, 60000);
  assert.equal(await waitForHaRefresh({lastSuccessAt: null}, async () => ({})), false);
});

test('stored integration connection with revoked OAuth is a demo blocker even with HTTP 200', () => {
  const result = apiSummary('/google', 200, {
    connected: true, configured: true,
    reauthorizationRequired: true, accountName: 'private@example.test', accessToken: 'secret'
  });
  assert.equal(result.passed, false);
  assert.equal(result.reauthorizationRequired, true);
  assert.ok(!JSON.stringify(result).includes('private'));
  assert.ok(!JSON.stringify(result).includes('secret'));
});

test('HA stale/offline/configuration states never become successful integration claims', () => {
  for (const body of [{configured: false}, {status: 'offline'}, {status: 'unknown'},
    {status: 'degraded'}, {connected: false}]) assert.equal(apiSummary('/ha', 200, body).passed, false);
  assert.equal(apiSummary('/ha', 200, {configured: true, status: 'healthy'}).passed, true);
});

test('provider errors and personal event payloads are reduced to bounded status/count metadata', () => {
  assert.deepEqual(apiSummary('/calendar', 409, {
    code: 'GOOGLE_REAUTHORIZATION_REQUIRED',
    error: 'provider-private-text'
  }), {
    check: '/calendar', passed: false, http: 409,
    code: 'GOOGLE_REAUTHORIZATION_REQUIRED'
  });
  assert.deepEqual(apiSummary('/calendar', 200, [{title: 'private event', token: 'secret'}]),
    {check: '/calendar', passed: true, http: 200, count: 1});
});

test('public smoke requires readiness bodies and denied unauthenticated device access', async () => {
  const fetcher = async (url) => {
    if (url.endsWith('/api/devices')) return new Response('', {status: 401});
    if (url.includes(':8080')) return Response.json({status: 'UP'});
    if (url.includes(':8020')) return Response.json({status: 'ready'});
    if (url.includes(':11434')) return Response.json({version: 'test'});
    return Response.json({status: 'ok'});
  };
  assert.ok((await publicSmoke(fetcher)).every((row) => row.passed));
  const exposed = await publicSmoke(async () => Response.json({status: 'loading'}));
  assert.equal(exposed.find((row) => row.check === 'tts').passed, false);
  assert.equal(exposed.find((row) => row.check === 'unauthenticated-device-access-denied').passed, false);
});
