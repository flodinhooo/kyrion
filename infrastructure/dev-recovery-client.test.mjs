import test from 'node:test';
import assert from 'node:assert/strict';
import {requestRecovery} from './dev-recovery-client.mjs';

test('a repeated start during the post-job cooldown starts once after bounded retry', async () => {
  let time = 0;
  let accepted = 0;
  const job = await requestRecovery(async (method) => {
    if (!method) return {state: 'completed'};
    if (time < 5000) throw Object.assign(new Error('busy'), {status: 409});
    accepted++;
    return {state: 'running', correlationId: 'one-job'};
  }, {action: 'start'}, {
    sleep: async (ms) => {
      time += ms;
    }
  });
  assert.equal(time, 5000);
  assert.equal(accepted, 1);
  assert.equal(job.correlationId, 'one-job');
});

test('concurrent starts join the running job without sending another mutation', async () => {
  const calls = [];
  const job = await requestRecovery(async (method) => {
    calls.push(method);
    return {state: 'running', correlationId: 'existing'};
  }, {action: 'start'});
  assert.deepEqual(calls, [undefined]);
  assert.equal(job.correlationId, 'existing');
});

test('restart never silently joins another job and permanent errors are not retried', async () => {
  await assert.rejects(requestRecovery(async () => ({state: 'running'}), {action: 'restart'}), /RECOVERY_BUSY/);
  let calls = 0;
  await assert.rejects(requestRecovery(async (method) => {
    calls++;
    if (!method) return {state: 'idle'};
    throw Object.assign(new Error('unauthorized'), {status: 401});
  }, {action: 'start'}), /unauthorized/);
  assert.equal(calls, 2);
});
