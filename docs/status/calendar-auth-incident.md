# Calendar authentication incident

## Current status

The local calendar UI currently redirects away from `/calendar` or loses the
visible authenticated workspace state. The issue is unresolved and must be
investigated before further calendar work continues.

## Observations

- The calendar API returns `401:UNAUTHENTICATED` in the affected browser flow.
- Direct unauthenticated requests to Core correctly return HTTP 401.
- Other authenticated Web requests such as devices and home data have worked
  during the same development session.
- Next.js development logs reported a stale module-factory error involving the
  AppShell bundle.

## Changes attempted

- Added dynamic rendering and no-store handling around the workspace/calendar
  route.
- Added client-side navigation to `/login` when the calendar API returns 401.
- Cleared the generated Next.js `.next` cache and restarted the Web dev
  process.
- Restored the original login-page behaviour that redirects an already
  authenticated user to `/`.

## Follow-up

Trace the browser request and redirect chain with the actual session cookie,
then compare the session used by the workspace layout with the session used by
`/api/calendar/events`. Do not change Core authentication, RBAC, or calendar
business logic until that boundary is isolated.
