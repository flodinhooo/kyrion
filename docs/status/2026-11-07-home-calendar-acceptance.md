# KY-001: real-stack native calendar verification

Result: four isolated authenticated scenarios pass. **Actual HOME/user acceptance
remains open.** No personal accounts, permissions, invitations, calendar/provider
data, installed runtimes, DNS or central identity settings were changed.

## Read-only inventory and test boundary

- Source baseline: `master` at `4f6ea01`, initially clean. Its completed maintenance
  CI was not repeated. The current calendar UI change is local and not pushed.
- Windows personal Core PID49944 remained running. Its guarded JAR SHA-256 matches
  the reviewed/tested artifact:
  `f73b47d1c55cc717804a77c88f07d23cf3ab807dc7714b03fb5e9f543b865130`.
  Its anonymous health probe returned UP; no personal session was opened. Personal
  Web PID25344 still uses Next16.2.11; its anonymous login form returned200.
  Existing personal Web/PostgreSQL were left running. Pi V46 is historical rollout evidence;
  no new Pi probe, update or restart was performed.
- Real Core/Java21, real PostgreSQL **17.10** with actual Flyway **V1–V46**, and a
  separate production Web build were used. The runner verifies matching tracked
  Web inputs and the supplied Core JAR hash. It creates new keys, tmpfs database
  storage and synthetic accounts on free loopback ports, without installation env.
- PostgreSQL was an existing local image, resolved by immutable image ID; no image
  update was performed. No Docker socket was mounted. The actual test browser was
  Chromium153.0.8010.12, Node24.19.0, time zone Europe/Zurich.
- There were **no simulated providers**. Google was disconnected/unconfigured;
  no connection or personal destination was seeded. An outbound HTTP(S) deny proxy
  and browser-origin guard recorded zero external attempts.

## Executed scenarios

| Combination | Viewport | Result |
| --- | --- | --- |
| German desktop | 1440 × 1000 | Pass |
| German mobile layout | 390 × 844 | Pass |
| English desktop | 1440 × 1000 | Pass |
| English mobile layout | 390 × 844 | Pass |

Each scenario performs seven grouped checkpoints, **28 total**:

1. Real password login in independent browser contexts with distinct server sessions.
2. Actual UI creation with explicitly selected A/B participants; persisted event
   and visibility in both sessions, no automatic personal-calendar delivery.
3. B edits through the UI; A reads the new canonical revision/time. B has no
   creator deletion action despite having calendar-delete permission in the fixture.
4. Two open editors: B saves revision2, A submits stale revision1. Actual HTTP409,
   exact `HOUSEHOLD_CALENDAR_CONFLICT`, translated feedback **fully in viewport**,
   and PostgreSQL's preserved latest title/revision are all asserted.
5. Participant B's forged delete and nonparticipant C's edit/delete return403.
   C can read the household event but sees read-only feedback. User D without
   calendar rights gets403; an unauthenticated context gets401. Denials preserve data.
6. Month/week/day controls, creator deletion through the UI, removal for A/B and
   real PostgreSQL audit actors: create A, edits B/B, delete A.
7. Logout, protected-route redirect and direct Core rejection of A's old token;
   B's independent session stays active.

Final database assertions: zero native test events, zero integration connections,
zero delivery rows. No page errors. Screenshots were inspected for desktop/mobile
feedback. This is responsive Chromium testing, not physical-phone/Safari acceptance.

## Reproduced defect and fix

The older UI stored the conflict text in the DOM but could leave it completely
outside the scrollable editor's visible area (English desktop: viewport ratio0).
An interim nearest-edge scroll still clipped a fraction of the paragraph. The
final change scrolls the existing editor feedback into view when a new message
appears. The regression requires the **entire** alert in viewport in all four cases;
no forced scrolling/clicking or reduced assertion threshold substitutes for it.
Revisions, Core permissions, participant rules and existing translations are unchanged.

Early automation attempts hit Chromium's CDP response-body retrieval error. The
final observer clones actual application responses inside the browser; it supplies
no fake response and retains exact error-code/status/data-preservation assertions.

## Checks and continuation

- Web ESLint, route generation/strict TypeScript, **262 existing unit tests** and
  isolated production build pass. No dependency/version or lockfile change.
- The new opt-in real-stack regression passes. Node syntax and targeted Prettier
  checks pass for its two helpers. No maintenance/hosted CI rerun or push occurred.
- [Runner instructions](../../infrastructure/dev/HOME_CALENDAR_ACCEPTANCE.md)
  explain the guarded fixture and required reviewed artifacts. Test helpers,
  report and the small UI correction are the only implementation scope.
- Ignored evidence: baseline/failed viewport probe under
  `.run/private-evidence/ky001-194e52b6/`, successful corrected runs under
  `.run/private-evidence/ky001-bb9e67ee/`, `ky001-864215af/` and `ky001-eb2fdafe/`.
  The last run also asserts direct Core-token revocation. Runtime manifests contain
  synthetic credentials and must not be committed. Owned processes and database
  containers were stopped after checks; existing personal processes were preserved.
- The [manual checklist](../home-family-calendar-manual-acceptance.md) names actual
  UI controls and separates installation access from isolated proof. The UI fix is
  **not installed** by this task. Actual two-user acceptance, real-provider
  disclosure/delivery/retry and physical mobile testing remain separate. **KY-001
  stays open**; no new accounts or invitations are authorized by this report.
