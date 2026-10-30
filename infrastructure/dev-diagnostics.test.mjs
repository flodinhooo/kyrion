import test from 'node:test';
import assert from 'node:assert/strict';
import {containerDiagnostic, classifyDockerLog, classifyKernelLog, windowsEventDiagnostic} from './dev-diagnostics.mjs';

test('diagnostics cannot persist credentials, container logs, commands or healthcheck output', () => {
  const result = containerDiagnostic({
    Name: '/kyrion-postgres', Config: {Env: ['PASSWORD=secret']},
    State: {
      Status: 'running', OOMKilled: false, ExitCode: 0, Error: 'private-token',
      StartedAt: '2026-10-30T17:46:29.877048196Z',
      Health: {Status: 'healthy', Log: [{Output: 'private-token'}]}
    }, RestartCount: 0
  });
  assert.equal(result.status, 'running');
  assert.equal(result.oomKilled, false);
  assert.equal(result.health, 'healthy');
  assert.ok(!JSON.stringify(result).includes('secret'));
  assert.ok(!JSON.stringify(result).includes('private-token'));
});

test('Windows crash correlation persists only classified metadata, never messages or command lines', () => {
  const result = windowsEventDiagnostic({
    events: [
      {
        at: '2026-10-30T17:43:26Z', id: 1000, code: 'WSL_DOCKER_PROCESS_FAILURE',
        Message: 'private-token', CommandLine: 'secret'
      },
      {at: '2026-10-30T17:43:26Z', id: 1, code: 'arbitrary-provider-payload'},
    ], unavailableLogs: ['Application', 'private path']
  });
  assert.deepEqual(result, {
    events: [{
      at: '2026-10-30T17:43:26Z', id: 1000,
      code: 'WSL_DOCKER_PROCESS_FAILURE'
    }], unavailableLogs: ['Application']
  });
  assert.ok(!JSON.stringify(result).includes('private'));
});

test('missing or malformed metadata remains unknown rather than claiming no OOM', () => {
  const result = containerDiagnostic({State: {OOMKilled: 'false', ExitCode: '0'}});
  assert.equal(result.oomKilled, null);
  assert.equal(result.exitCode, null);
  assert.equal(result.health, 'unknown');
});

test('WSL reset correlation uses outer timestamps and drops provider log payloads', () => {
  const result = classifyDockerLog('[2026-10-30T17:43:26.1Z][backend] Wsl/Service/0x80072746 secret\n'
    + '[2026-10-30T17:43:27.0Z][backend] setting engine linux/wsl state running -> stopping\n'
    + 'untrusted payload Wsl/Service/0x80072746');
  assert.deepEqual(result, [{at: '2026-10-30T17:43:26.1Z', code: 'wslConnectionReset'},
    {at: '2026-10-30T17:43:27.0Z', code: 'engineStopping'}]);
});

test('GPU query warnings and recovery init timeouts are not misclassified as OOM or panic', () => {
  const result = classifyKernelLog('dxgkio_query_adapter_info: Ioctl failed: -2\n'
    + 'WaitForBootProcess:3352: /sbin/init failed to start within 10000\n'
    + 'potentially unexpected fatal signal 5.');
  assert.deepEqual(result, {
    oomEvents: 0, panics: 0, initTimeouts: 1, dxgWarnings: 1,
    interopFatalSignals: 1
  });
  assert.equal(classifyKernelLog('Out of memory: Killed process 123 (python)').oomEvents, 1);
});
