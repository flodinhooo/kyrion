import test from 'node:test';
import assert from 'node:assert/strict';
import {waitUntilReady, serviceReady, inspectService, startDatabase} from './dev-readiness.mjs';

function clock() {
  let time = 0;
  return {now: () => time, sleep: async (ms) => { time += ms; }, timeoutMs: 600_000};
}

test('probe diagnostics distinguish timeout, HTTP failure and invalid bodies without logging payloads', async () => {
  const service = {id: 'core', port: 8080};
  assert.equal((await inspectService(service, async () => {
    throw new DOMException('private', 'TimeoutError');
  })).code, 'PROBE_TIMEOUT');
  assert.equal((await inspectService(service, async () => new Response('private', {status: 503}))).code, 'HTTP_503');
  assert.equal((await inspectService(service, async () => new Response('not JSON'))).code, 'INVALID_RESPONSE');
  const result = await inspectService(service, async () => {
    throw new Error('secret credential');
  });
  assert.equal(result.code, 'UNREACHABLE');
  assert.ok(!JSON.stringify(result).includes('secret'));
  assert.equal((await inspectService(service, async () => Response.json({status: 'UP'}))).ready, true);
});

test('cold database recovery can exceed Compose health retries without starting Core early', async () => {
  let attempts = 0;
  const calls = [];
  const ready = await startDatabase(async (file, args) => {
    calls.push(args);
    if (args[0] === 'exec' && ++attempts < 320) throw new Error('starting up');
  }, clock());
  assert.equal(ready, true);
  assert.equal(attempts, 320);
  assert.ok(calls[0].includes('--no-recreate'));
  assert.ok(!calls.flat().includes('--wait'));
  assert.ok(!calls.flat().some((arg) => ['restart', 'down', 'rm'].includes(arg)));
});

test('permanent database failure is bounded and returns failure to its caller', async () => {
  let calls = 0;
  assert.equal(await startDatabase(async () => {
    if (++calls > 1) throw new Error('unavailable');
  }, {...clock(), timeoutMs: 2000}), false);
  assert.equal(calls, 4);
});

test('slow TTS is awaited; exited processes and deadlines stop polling', async () => {
  let probes = 0;
  assert.equal(await waitUntilReady(async () => ++probes === 620, {...clock(), timeoutMs: 900_000}), true);
  assert.equal(await waitUntilReady(async () => false, {...clock(), alive: () => false}), false);
  assert.equal(await waitUntilReady(async () => false, {...clock(), timeoutMs: 2000}), false);
});

test('a listening but loading, failed, malformed or unrelated service is not healthy', async () => {
  for (const [id, body] of [['core', {status: 'UP'}], ['ai', {status: 'ok'}],
    ['stt', {status: 'ok'}], ['tts', {status: 'ready'}], ['ollama', {version: '1.0'}]]) {
    const service = {id, port: 1234};
    assert.equal(await serviceReady(service, async () => Response.json(body)), true);
    for (const value of [null, {}, {status: 'loading'}, {status: 'DOWN'}]) {
      assert.equal(await serviceReady(service, async () => Response.json(value)), false);
    }
    assert.equal(await serviceReady(service, async () => new Response('invalid')), false);
    assert.equal(await serviceReady(service, async () => Response.json(body, {status: 503})), false);
    assert.equal(await serviceReady(service, async () => { throw new Error('connection refused'); }), false);
  }
});
