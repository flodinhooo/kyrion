# KY-001: manual HOME/calendar acceptance

**OPEN: actual user acceptance is still required.** The
[isolated real-stack checks](status/2026-11-07-home-calendar-acceptance.md) do not
close this gate. This checklist has not been executed on personal accounts/data.

## Target and prerequisites

- Choose **one** installation: Windows `http://localhost:3000`, or the existing
  Pi installation `https://kyrion-node.local`. Never mix their accounts or data.
  The Windows Core artifact was checked read-only; Pi readiness was not reprobed.
- Two existing active local accounts A and B in the same HOME Space, their own
  passwords and current calendar permissions. A needs read/create/update/delete; B
  needs read/update. If a prerequisite is absent, stop: do not create accounts,
  send invitations or change permissions as part of this checklist.
- Use two separate browser profiles or browsers, not two ordinary tabs sharing
  cookies. Repeat in German/English and desktop/mobile; record the actual device,
  viewport, time zone, installation and software version.
- Windows loopback works only on that PC; resize its browser for a mobile-layout
  check. A real phone may use the Pi HTTPS address only if already reachable and
  trusted. Do not change networking, certificates or DNS to enable this test.
- Obtain the owner's approval to create/delete only clearly marked synthetic
  **Kyrion household events**. Do not use existing family events, connect Google,
  select personal delivery destinations or change provider/account configuration.
- The conflict-feedback fix is currently a **local source change**, not an update
  of either personal installation. Do not assume the installed Web contains it.
  An update requires separate authorization. Record an offscreen warning as a
  failed UX check, even if scrolling reveals it.

## Perform later with the owner

| Step | Exact surface/action | Expected result |
| --- | --- | --- |
| 1 | A and B each open `/login` and use their own local password. In the sidebar choose **Kalender / Calendar** (`/calendar`). | Both sessions are authenticated independently; no central-account link or invitation is needed. Never share passwords or record them in evidence. |
| 2 | A chooses **Gemeinsamen Termin erstellen / Create shared event**. Set **Titel / Title** to `KY-001 manual <date>`, a synthetic description and an ordinary timed slot under **Beginn / Start** and **Ende / End**. Select B explicitly; A is already selected. Do not use **Alle auswählen / Select everyone**. **Speichern / Save**. | Exactly the intended A/B participants; one native household event. Saving does not send personal calendar copies. |
| 3 | B uses **Aktualisieren / Refresh**, opens the event, changes its title to append `B1`, then saves. A refreshes/reopens it. | B's edit is persisted and visible to A on the same event, with the intended time. |
| 4 | Both open the saved `B1` event. B changes it to `B2` and saves. A edits the still-open older form and saves. | A receives **Dieser Termin wurde inzwischen geändert… / This event has changed…**, readable inside the dialog without searching below the fold. A's stale changes do not overwrite B2. A cancels, refreshes and reopens: B2 remains. |
| 5 | In B's editor inspect the actions. A then uses **Löschen / Delete** and confirms deletion of this marked native event. B refreshes. | B has no creator deletion action; A can delete with its existing permissions. The event disappears for both. No provider copy is deleted. |
| 6 | Optional negative case using the same two accounts: A creates another marked shared event selecting **only A**. B refreshes and opens/clicks it. A subsequently deletes that test event. | Household members with calendar read permission can still see native household events. B is not a participant, so cannot edit/delete this one. Participants control editing, not private visibility. |
| 7 | B uses **Abmelden / Sign out**, then opens `/calendar`. Check A separately. | B is redirected to login; A's separate session remains usable. Complete the owner-observed local login/logout check on the intended installation. |

Record pass/fail/not-run per step, DE/EN and device, with redacted screenshots and
correlation IDs where available. Do not retain passwords or personal event text.
Delete only the marked native events you created; do not perform bulk cleanup.

## Still separate

Unauthenticated/no-calendar permission denials and creator-only deletion were
checked against real Core/PostgreSQL in isolation, without changing personal roles.
Real Google disclosure/revocation, selected delivery, retry/conflict and copy
retention remain **not accepted**; they need a separately authorized disposable
provider-calendar procedure. See [HOME readiness](home-first-use-readiness.md).
No simulated or isolated result closes **KY-001**.
