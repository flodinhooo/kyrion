# Pi HOME Web conflict-feedback rollout

2026-11-07. **Installed on Pi; actual KY-001 user acceptance remains open.**
The owner authorized only the Web update and its short restart. No Windows
update, push, public website deployment, account/calendar change or provider
action was performed.

## Active artifact

- Target: `kyrion-node`, `https://kyrion-node.local`, native ARM64.
- Source: `871c46a700249ff848e78303b65263b5e7612307`.
- Web: `kyrion/web:ky001-871c46a-20261107`;
  image `sha256:9f1a00ed82b3fef847f32a121a793b8cff76aeddbb4b8080bebf66da241ca3e8`.
- Build: `aaUX9C2_I6tMOcrV1sImr`; container
  `2aec8a764ad4ece66c187ce8a66b1ae7d589be2619768c0b60345f2e1abd9300`,
  started `2026-11-07T12:15:03Z`.
- Separate Git archive and frozen-lockfile production build; Node base pinned
  to the prior rollout digest. No dependency or Core artifact upgrade.

## Initial refusal and correction

The first owner-run activation stopped before changing any installed file or
container. The operator script incorrectly compared the normal Compose hash
with a container previously created using `up --no-deps`. That operation removes
the service dependency model before hashing. Reproducing only that normalization
with the protected previous deployment yields the exact running Web hash.

The corrected guard normalizes only `depends_on`, only when the running
dependency label is explicitly empty. The remaining effective configuration
still has to match the running hash. Checks reject changed image, environment
URL and read-only mode, and reject normalization for a nonempty dependency label.
The actual root-only installed configuration passed the corrected guard before
activation. The candidate's complete effective configuration differed only in
`web.image`; no drift was accepted. The owner-established sudo authorization
then allowed the scoped activation without collecting or logging a password.

## Verification and preservation

- Exact new image: four anonymous DE/EN desktop/mobile browser cases passed
  in an internal network with a **simulated anonymous Core setup/config** only.
- Actual updated HTTPS Pi: four DE/EN desktop/mobile login browser cases passed,
  normal TLS validation, username/password fields, anonymous API401 and protected
  profile redirect, no JavaScript errors, failed assets or external requests.
- Actual new build ID verified inside Web. The served conflict-fix client chunk
  exactly matches the prepared image's SHA-256. No authenticated calendar claim
  is inferred from these anonymous checks.
- Web healthy; Core `UP`; PostgreSQL and Caddy healthy. All other existing Pi
  container IDs, image IDs and start times remain unchanged. Core JAR unchanged;
  schema metadata remains successful V46, queried only in a read-only transaction.
- Environment, TLS, original secret files and their ownership/modes were checked
  unchanged. No migration, database restore, account/permission/invitation change,
  calendar mutation, hardware action or provider call was performed.
- Windows Core/Web process IDs and original start times remain unchanged.
- Existing [28-point real-stack proof](2026-11-07-home-calendar-acceptance.md)
  was preserved, not repeated. **No rollback was required.**

## Recovery and next gate

The old Web image remains retained and archived privately on the Pi. Original
Compose/environment and activation/verification evidence are under
`/var/backups/kyrion/web-ky001-871c46a-20261107` (root0700; backup files0600).
The operator script at
`/home/flodinho/.local/state/kyrion/web-ky001-871c46a-20261107/activate-web.py`
has a `rollback` action: restore the previous Web image after a concurrent-edit
guard, recreate only Web, then verify the old build and unchanged other services.
No SQL rollback or session revocation is part of that path.

Ignored local evidence: `.run/private-evidence/ky001-pi-web/activation-result.json`,
`updated-live-browser-results.json`, synthetic-image browser results and screenshots.
Private inspection/configuration files remain protected on the Pi.

Reload existing browser pages before the
[two-user manual acceptance](../home-family-calendar-manual-acceptance.md).
Existing Core sessions are not deliberately revoked, but live session retention
was not tested with personal accounts. Unsaved forms can be lost on reload.
Physical-phone, authenticated family and real-provider acceptance remain open.

## Subsequent KY-002 Web activation and read-only confirmation

The owner completed the separately prepared KY-002 Web activation and supplied
`ACTIVATION_VERIFIED`: new build `N6PUtpaaokUmjYzUdfjFf`, Core UP, schema46,
normal HTTPS/login/assets, unchanged other containers and protected settings.
The activation was **not repeated** and no rollback was run by this follow-up.

Read-only inspection confirms active image
`sha256:bf79063124a2354e1ecabebb00221055f8058a4889e614b1298b064af6db5882`,
reference `kyrion/web:ky002-90125b9-20261107`, exact new build, healthy Web and
Core UP. Web container is
`c97f2b290786e5f1cc05294a919a75160593f84508cfc5dd69a2f8c021c0f829`, started
`2026-11-07T17:29:12.435191936Z`. This supersedes this report's earlier active
871c46a artifact; that earlier activation remains historical evidence.

The current slot's root-protected original Compose/environment, preflight,
activation and result receipts are under
`/var/backups/kyrion/web-ky002-90125b9-20261107/`, as established by the
owner-run operator. The agent cannot independently reread those root-only
receipts through noninteractive sudo; no password or broader access was sought.
Current staging/evidence remains at
`/home/flodinho/.local/state/kyrion/activation-90125b9-20261107/`.
The immediate Web rollback target is build `aaUX9C2_I6tMOcrV1sImr`, not the
older pre-KY-001 build. No rollback is requested or performed.

The installed Web now presents grant/review status and selected-binding save
semantics. It does not create grants by deployment. An anonymous API request
returns401; no authenticated human session is available to this agent. The
owner-confirmed three Pi assignments are still legacy rows with null grants,
actors and source-node fields. Their source/room/action mapping matches the
reviewed inventory. Saving is blocked on a legitimate eligible human session;
no SQL authorization, synthetic session or device command was used. Physical
button and authenticated HOME acceptance remain open. Windows is untouched.
