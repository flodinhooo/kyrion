import test from 'node:test';
import assert from 'node:assert/strict';
import {EventEmitter} from 'node:events';
import {commandSucceeded} from './dev-command.mjs';

function fixture() {
  const child = new EventEmitter();
  let timeout;
  let cleared = false;
  let killed = false;
  let unreferenced = false;
  child.kill = () => {
    killed = true;
  };
  child.unref = () => {
    unreferenced = true;
  };
  const promise = commandSucceeded('docker.exe', ['exec', 'kyrion-postgres'], {
    spawnProcess: (file, args, options) => {
      assert.equal(file, 'docker.exe');
      assert.equal(args[0], 'exec');
      assert.equal(options.windowsHide, true);
      assert.equal(options.stdio, 'ignore');
      return child;
    },
    setTimer: (callback) => {
      timeout = callback;
      return 1;
    },
    clearTimer: () => {
      cleared = true;
    },
  });
  return {child, promise, expire: () => timeout(), state: () => ({cleared, killed, unreferenced})};
}

test('a hung Docker client cannot indefinitely block status even without an exit event', async () => {
  const f = fixture();
  f.expire();
  assert.equal(await f.promise, false);
  assert.deepEqual(f.state(), {cleared: false, killed: true, unreferenced: true});
});

test('SQL readiness requires successful client exit and clears its deadline', async () => {
  for (const code of [0, 1, null]) {
    const f = fixture();
    f.child.emit('exit', code);
    assert.equal(await f.promise, code === 0);
    assert.deepEqual(f.state(), {cleared: true, killed: false, unreferenced: false});
  }
});

test('missing Docker is reported as unavailable', async () => {
  const f = fixture();
  f.child.emit('error', new Error('ENOENT'));
  assert.equal(await f.promise, false);
  assert.equal(f.state().cleared, true);
});
