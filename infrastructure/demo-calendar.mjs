import {randomUUID} from 'node:crypto';

export function disposableEvent(event, id, marker) {
  return typeof id === 'string' && /^[a-f0-9-]{36}$/.test(id) && event?.id === id
    && event.source === 'local' && event.title.startsWith(marker)
    && event.syncToGoogle === false && !event.googleEventId && !event.googleCalendarId;
}

// Creates only an explicitly marked local test event; never calls Google sync.
export async function localCalendarSmoke(api, csrf) {
  const marker = `[KYRION-DEMO-SMOKE ${randomUUID()}]`;
  const body = {
    title: marker, description: 'Disposable local stabilization check.',
    startsAt: '2026-10-31T14:00:00Z', endsAt: '2026-10-31T14:15:00Z',
    timeZone: 'Europe/Zurich', syncToGoogle: false
  };
  const headers = {'x-kyrion-csrf': csrf};
  const rows = [];
  let id;
  let revision;
  try {
    const created = await api.post('/api/calendar/events', {headers, data: body, timeout: 15000});
    if (!created.ok()) return [{check: 'local-calendar-create', passed: false, http: created.status()}];
    const event = await created.json();
    id = event.id;
    revision = event.revision;
    rows.push({check: 'local-calendar-create', passed: !!id && event.syncToGoogle === false});
    if (typeof id !== 'string' || !/^[a-f0-9-]{36}$/.test(id)) return rows;
    const edited = await api.put(`/api/calendar/events/${id}`, {
      headers, data: {...body, title: marker + ' edited', revision}, timeout: 15000,
    });
    rows.push({check: 'local-calendar-update', passed: edited.ok()});
    if (!edited.ok()) return rows;
    const updated = await edited.json();
    const stale = await api.put(`/api/calendar/events/${id}`, {
      headers, data: {...body, revision}, timeout: 15000,
    });
    rows.push({check: 'local-calendar-stale-revision-rejected', passed: stale.status() === 409});
    revision = updated.revision;
    const read = await (await api.get('/api/calendar/events', {timeout: 15000})).json();
    const persisted = read.items?.find((item) => item.id === id);
    rows.push({
      check: 'local-calendar-timezone-persistence', passed: disposableEvent(persisted, id, marker)
        && persisted.timeZone === body.timeZone && Date.parse(persisted.startsAt) === Date.parse(body.startsAt)
    });
  } finally {
    if (typeof id === 'string' && /^[a-f0-9-]{36}$/.test(id)) {
      const read = await (await api.get('/api/calendar/events', {timeout: 15000})).json();
      const event = read.items?.find((item) => item.id === id);
      // Re-read and verify our exact marker/local-only scope before deletion.
      if (disposableEvent(event, id, marker)) {
        const removed = await api.delete(`/api/calendar/events/${id}?revision=${event.revision}`, {
          headers,
          timeout: 15000
        });
        const final = await (await api.get('/api/calendar/events', {timeout: 15000})).json();
        rows.push({
          check: 'local-calendar-test-object-cleanup', passed: removed.status() === 204
            && !final.items?.some((item) => item.id === id)
        });
      } else rows.push({check: 'local-calendar-test-object-cleanup', passed: false, code: 'SCOPE_CHANGED_PRESERVED'});
    }
  }
  return rows;
}
