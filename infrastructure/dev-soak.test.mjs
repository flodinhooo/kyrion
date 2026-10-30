import test from 'node:test';
import assert from 'node:assert/strict';
import {observeServices} from './dev-soak.mjs';

test('a temporary outage remains recorded after recovery instead of becoming an all-green claim', async () => {
  let time = 0;
  const result = await observeServices({
    durationMs: 3000, intervalMs: 1000,
    now: () => time, sleep: async (ms) => {
      time += ms;
    },
    probe: async () => [{id: 'core', ready: time !== 1000}, {id: 'tts', ready: true}],
  });
  assert.equal(result.samples, 4);
  assert.equal(result.failureCount, 1);
  assert.deepEqual(result.failures, [{service: 'core', offsetMs: 1000}]);
  assert.equal(result.elapsedMs, 3000);
});

test('soak duration is bounded and long failures retain counts without unbounded logs', async () => {
  let time = 0;
  const result = await observeServices({
    durationMs: 200, intervalMs: 1,
    now: () => time, sleep: async (ms) => {
      time += ms;
    },
    probe: async () => [{id: 'tts', ready: false}],
  });
  assert.equal(result.failureCount, 201);
  assert.equal(result.failures.length, 100);
});
