# Calendar authentication incident

## Status

RESOLVED

## Root cause

The Core authentication interceptor did not include `/v1/calendar/**` in its
registered path patterns. Consequently, a request could contain a valid Bearer
token without receiving the authenticated user and workspace context.

The Calendar controller then called `workspaceOwnerId()`, which found no
authenticated context and threw `UnauthenticatedException`.

## Additional runtime factor

After the source fix was applied, an older Kyrion Core process continued to
run on port 8080. It had been started before the source change and therefore
used the old compiled class state.

The fix became active only after that process was stopped and Core was cleanly
restarted from the current repository state.

## Runtime verification

- `/v1/calendar/events` is matched by `AuthenticatedRouteInterceptor`.
- The browser successfully loads local calendar events.
- A local test event is displayed in the calendar UI.

## Resolution

Core now applies the existing authentication interceptor to `/v1/calendar/**`.
The existing Web session validation and Bearer forwarding remain unchanged.

## Separate follow-up work

The following items are outside this incident and are not remaining incident
work:

- Correct selected-date handling when creating events.
- Google Calendar event integration and synchronization.
- Calendar UX and details.
