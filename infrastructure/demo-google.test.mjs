import test from 'node:test';
import assert from 'node:assert/strict';
import {ownedGoogleTest} from './demo-google.mjs';

test('Google cleanup requires our generated ID, exact marker, description, ETag and nonrecurring scope', () => {
  const id = 'k' + 'a'.repeat(32);
  const marker = '[KYRION-GOOGLE-SMOKE unique]';
  const description = 'unique disposable marker';
  const event = {id, summary: marker, description, etag: 'v1', recurring: false};
  assert.equal(ownedGoogleTest(event, id, marker, description), true);
  assert.equal(ownedGoogleTest({...event, summary: marker + ' edited'}, id, marker, description), true);
  for (const change of [{id: 'personal'}, {summary: 'personal'}, {description: 'personal'},
    {recurring: true}, {etag: ''}]) {
    assert.equal(ownedGoogleTest({...event, ...change}, id, marker, description), false);
  }
  assert.equal(ownedGoogleTest(event, 'arbitrary-existing-id', marker, description), false);
});
