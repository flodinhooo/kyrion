import {randomUUID} from 'node:crypto';

export function ownedGoogleTest(event, id, marker, description) {
  return typeof id === 'string' && /^k[0-9a-f]{32}$/.test(id) && event?.id === id
    && (event.summary === marker || event.summary === marker + ' edited')
    && event.description === description && event.recurring === false
    && typeof event.etag === 'string' && event.etag.length > 0;
}

// Only a newly marked provider event is mutated. Never invoke actor-wide sync.
export async function googleCalendarSmoke(api, csrf) {
  const rows = [];
  const status = await (await api.get('/api/integrations/google')).json();
  if (!status.connected || status.reauthorizationRequired) return [
    {check: 'google-authorized', passed: false, code: 'GOOGLE_NOT_READY'},
  ];
  rows.push({check: 'google-authorized-without-new-oauth', passed: true});
  const calendars = await (await api.get('/api/integrations/google/calendar/calendars')).json();
  const writable = calendars.items?.filter((item) => ['owner', 'writer'].includes(item.accessRole)) ?? [];
  const calendar = writable.find((item) => !item.primary) ?? writable.find((item) => item.primary);
  if (!calendar) return [...rows, {check: 'google-test-calendar', passed: false, code: 'NO_WRITABLE_CALENDAR'}];
  const id = 'k' + randomUUID().replaceAll('-', '');
  const marker = `[KYRION-GOOGLE-SMOKE ${randomUUID()}]`;
  const description = `Disposable Kyrion verification ${randomUUID()}; no attendees or personal data.`;
  const headers = {'x-kyrion-csrf': csrf};
  const query = new URLSearchParams({
    calendarId: calendar.id,
    start: '2026-10-31T00:00:00+01:00', end: '2026-11-01T00:00:00+01:00'
  });
  const listing = `/api/integrations/google/calendar/events?${query}`;
  const body = {
    id, calendarId: calendar.id, summary: marker, description,
    start: '2026-10-31T07:10:00+01:00', end: '2026-10-31T07:15:00+01:00'
  };
  let attempted = false;
  const readOwn = async () => {
    const response = await api.get(listing, {timeout: 30000});
    if (!response.ok()) throw new Error('GOOGLE_READ_FAILED');
    const value = await response.json();
    if (!Array.isArray(value.items)) throw new Error('GOOGLE_INVALID_RESPONSE');
    return value.items.filter((item) => item.id === id);
  };
  try {
    attempted = true;
    const created = await api.post('/api/integrations/google/calendar/events', {headers, data: body, timeout: 30000});
    rows.push({check: 'google-marked-event-create', passed: created.ok(), http: created.status()});
    if (!created.ok()) return rows;
    const matches = await readOwn();
    const event = matches[0];
    const owned = matches.length === 1 && ownedGoogleTest(event, id, marker, description);
    rows.push({
      check: 'google-stable-id-and-offset-range', passed: owned
        && Date.parse(event.start) === Date.parse(body.start) && Date.parse(event.end) === Date.parse(body.end)
    });
    if (!owned) return rows;
    const edited = await api.put(`/api/integrations/google/calendar/events/${id}`, {
      headers, data: {...body, summary: marker + ' edited', etag: event.etag}, timeout: 30000,
    });
    rows.push({check: 'google-conditional-edit', passed: edited.ok(), http: edited.status()});
    if (!edited.ok()) return rows;
    const stale = await api.put(`/api/integrations/google/calendar/events/${id}`, {
      headers, data: {...body, etag: event.etag}, timeout: 30000,
    });
    rows.push({check: 'google-stale-etag-rejected', passed: stale.status() === 409, http: stale.status()});
    const combined = await (await api.get(`/api/calendar/events?${query}`, {timeout: 30000})).json();
    const imported = combined.items?.find((item) => item.id === `google:${id}`);
    rows.push({
      check: 'google-provider-edit-visible-in-kyrion', passed: combined.google?.status === 'ready'
        && imported?.title === marker + ' edited' && Date.parse(imported.startsAt) === Date.parse(body.start)
    });
  } finally {
    if (attempted) {
      const matches = await readOwn();
      if (matches.length === 0) rows.push({check: 'google-test-object-cleanup', passed: true, code: 'ALREADY_ABSENT'});
      else if (matches.length === 1 && ownedGoogleTest(matches[0], id, marker, description)) {
        const search = new URLSearchParams({calendarId: calendar.id, etag: matches[0].etag});
        const deleted = await api.delete(`/api/integrations/google/calendar/events/${id}?${search}`, {
          headers,
          timeout: 30000
        });
        rows.push({
          check: 'google-test-object-cleanup', passed: deleted.status() === 204
            && (await readOwn()).length === 0, http: deleted.status()
        });
      } else rows.push({check: 'google-test-object-cleanup', passed: false, code: 'SCOPE_CHANGED_PRESERVED'});
    }
  }
  return rows;
}
