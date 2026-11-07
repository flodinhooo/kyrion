# KY-001: authenticated HOME/calendar acceptance

Status: prepared, **not executed or accepted**. KY-001 remains open.
Use the [active backlog](status/TODO.md) and
[current readiness boundaries](home-first-use-readiness.md).

## Prerequisites

- An owner-controlled test installation on the intended reviewed runtime, one
  HOME Space, and two existing active local accounts A and B with calendar
  read/create/edit permissions. A can be the OWNER. No new invitation is required
  by this checklist. Keep personal installations and data outside this fixture.
- Two independent browser profiles; run DE and EN at desktop and mobile widths.
  Record runtime/version, browser, locale, viewport, time zone and actual results.
- The actual intended installation additionally needs an owner-observed local
  password login/logout check. Keep that check read-only, without modifying the
  owner account. A sandbox login cannot close this production-journey gate.
- For the optional real-provider stage, separately authorized Google test
  accounts, valid connections, and dedicated disposable calendars containing
  synthetic events only. Stop that stage if unavailable; do not substitute a
  personal calendar, reconnect a personal account or infer provider acceptance.
- No AI, central identity, device action, recurring/all-day authoring or automatic
  delivery is needed. Do not change roles or personal account settings for this run.

## Native household flow

1. In profile A, log in using the existing local password. Open Calendar, reload
   and confirm the session remains authenticated. Log B in separately. After
   logout, protected calendar access must return to login; repeat normal login.
2. A chooses **Create shared event**, names it `KY-001 synthetic`, sets an ordinary
   timed slot in the recorded browser time zone and explicitly selects A and B.
   Save. Both profiles must show one shared household event after refresh, with
   the correct participants and time. Saving alone must not write Google copies.
3. B edits the title/time and saves; A reloads and sees the same updated event.
   Keep an old event editor open in A, save another edit in B, then attempt A's
   stale save: show a conflict/reload message and preserve B's accepted change.
4. Check month/week/day views, person filters and long dialogs on desktop/mobile.
   Hiding an entry with a filter must not change consent or event data. Reopen
   without changing its time and save: the instant must remain unchanged,
   including a prearranged DST fixture. Do not claim an ambiguous-time chooser.
5. B must not have creator deletion authority. Delay A's deletion until after
   provider checks if those will run. In the native-only run, A confirms deletion;
   both profiles must lose the household event after refresh.

## Separately authorized Google test stage

6. Using only a synthetic event in B's disposable personal calendar, verify the
   initial **Private** setting exposes nothing to A. B explicitly shares **Event
   times only**: A sees busy intervals without title/description. B switches to
   **Event details** with confirmation: A may read those details. A's OWNER role
   alone grants no private access. Reading does not authorize personal edits.
7. B revokes sharing. A's visible view refreshes/clears the shared data and a new
   read is denied. Record actual refresh timing; already seen/copied information
   cannot be recalled. UI filtering is not a substitute for this revocation.
8. B explicitly allows joint-event copies in its disposable writable destination
   under **Receive shared events in my Google calendar**. A saves a joint event,
   selects only B under **Send saved event to selected calendars**, and confirms.
   Check B's individual delivery status and the actual single Google copy.
   Resend/update the saved revision: no duplicate; status/revision match the copy.
9. Modify that synthetic Google copy externally, then attempt delivery of a newer
   native revision: preserve the external edit and show conflict/review status.
   If an outcome is uncertain, refresh status before retrying; do not assume no
   copy exists. For a controlled browser-network failure, verify understandable
   failure and a subsequent idempotent retry. This alone does not certify an
   upstream provider outage or every failure boundary.
10. B withdraws the test destination. Future writes/retries must stop; existing
    copies remain. A then confirms native deletion: both profiles lose the shared
    event, while personal Google copies remain with no further household updates.
    Provider-copy deletion is not implemented. Cleanup of synthetic provider data
    is a separate explicit operator action in the disposable calendars.

## Evidence and decision

Record pass/fail/not-run per step and each DE/EN desktop/mobile combination,
observed errors, redacted screenshots and relevant correlation IDs. Never record
passwords, tokens or personal calendar content. A runtime health probe, anonymous
page load or automated browser fixture is insufficient. Keep KY-001 open until
the owner reviews actual authenticated and real-provider evidence, including any
not-run failure/DST cases. This document does not authorize executing the steps.
