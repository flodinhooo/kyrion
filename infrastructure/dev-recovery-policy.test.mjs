import test from 'node:test';
import assert from 'node:assert/strict';
import {authorisedKey, validAction, canRestartManagedProcess, selectedServices} from './dev-recovery-policy.mjs';

test('operator authentication requires the complete exact ASCII key', () => {
  const key = 'a'.repeat(64);
  assert.equal(authorisedKey(key, key), true);
  for (const input of [undefined, '', 'a', 'b'.repeat(64), 'é'.repeat(64)]) {
    assert.equal(authorisedKey(input, key), false);
  }
});

test('scoped restart accepts only existing Windows services and excludes WSL/DB/Pi/commands', () => {
  for (const service of ['core', 'ai', 'ollama']) assert.equal(validAction({action: 'restart', service}), true);
  for (const service of ['postgres', 'tts', 'stt', 'web', 'voice-satellite', '../core', 'core;whoami']) {
    assert.equal(validAction({action: 'restart', service}), false);
  }
  assert.equal(validAction({action: 'start', service: 'core'}), false);
  assert.equal(validAction({action: 'restart', service: 'core', command: 'whoami'}), false);
  const services = [{id: 'core'}, {id: 'ai'}, {id: 'tts'}];
  assert.deepEqual(selectedServices(services, 'core'), [{id: 'core'}]);
  assert.deepEqual(selectedServices(services, 'invalid'), []);
  assert.equal(selectedServices(services), services);
});
test('only fixed start and restart actions are accepted', () => {
  assert.equal(validAction({action: 'start'}), true);
  assert.equal(validAction({action: 'restart'}), true);
  for (const input of [null, {}, {action: 'stop'}, {action: 'start', command: 'whoami'}, {action: ['start']}]) {
    assert.equal(validAction(input), false);
  }
});
test('restart preserves WSL even when its client is managed and alive', () => {
  const child = {exitCode: null, killed: false};
  assert.equal(canRestartManagedProcess('restart', 'wsl.exe', child), false);
  assert.equal(canRestartManagedProcess('restart', 'java.exe', child), true);
  assert.equal(canRestartManagedProcess('restart', 'python.exe', child), true);
});
test('only a live managed process can restart; start never terminates it', () => {
  assert.equal(canRestartManagedProcess('restart', 'java.exe', undefined), false);
  assert.equal(canRestartManagedProcess('restart', 'java.exe', {exitCode: 0, killed: false}), false);
  assert.equal(canRestartManagedProcess('restart', 'java.exe', {exitCode: null, killed: true}), false);
  assert.equal(canRestartManagedProcess('start', 'java.exe', {exitCode: null, killed: false}), false);
});
