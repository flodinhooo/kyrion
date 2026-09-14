# Calendar view handoff

## Status

Paused for the next work session. The current Calendar slice is implemented
and verified for local events and read-only Google Calendar display.

## Implemented

- Calendar authentication incident is resolved and documented separately in
  `docs/status/calendar-auth-incident.md`.
- Clicking a calendar day passes that selected local date into the event
  creation editor.
- Default event times remain sensible while preserving the selected date and
  local timezone.
- The existing local Calendar GET flow also reads Google events through the
  existing Google Calendar read endpoint.
- Local and Google events are normalized into one view model.
- Local IDs remain unchanged; Google IDs use a `google:` prefix to avoid
  collisions.
- Google events are displayed read-only and are marked as Google events in the
  Calendar view.
- Local events remain available when Google is disconnected or unavailable.
- Local event CRUD remains unchanged.

## Verification

- Web Vitest: 37 test files, 96 tests passed.
- Web ESLint: passed.
- Web TypeScript check: passed.
- Web production build: passed.
- Core `compileKotlin`: passed.

## Continue next time

- Verify and refine the selected-date creation flow in the running browser.
- Review the Google event presentation and detail behavior.
- Define the next bounded step for real bidirectional Google Calendar sync.

## Explicitly deferred

These items are outside the current handoff and remain future work:

- Full bidirectional Google Calendar synchronization.
- Production-ready Google write/update/delete synchronization semantics.
- Broader Calendar UX and details.
