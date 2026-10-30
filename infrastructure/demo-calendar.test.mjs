import test from 'node:test';
import assert from 'node:assert/strict';
import {disposableEvent} from './demo-calendar.mjs';

test('cleanup can never delete personal, remote, linked or differently marked records', () => {
  const id = '12345678-1234-1234-1234-123456789abc';
  const marker = '[KYRION-DEMO-SMOKE unique]';
  const event = {id, title: marker + ' edited', source: 'local', syncToGoogle: false};
  assert.equal(disposableEvent(event, id, marker), true);
  for (const change of [{title: 'personal'}, {source: 'google'}, {syncToGoogle: true},
    {googleEventId: 'remote'}, {googleCalendarId: 'primary'}, {id: 'different'}]) {
    assert.equal(disposableEvent({...event, ...change}, id, marker), false);
  }
});
