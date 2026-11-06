# Service recovery and Pi update preparation

Latest outcome: [successful November 6 activation](2026-11-06-pi-update-activation.md)
supersedes the pending-activation status below.

Continuation on 2026-11-06: the operator's sudo authorization now permits the
administrative connection. The original V30 platform and both candidate image
IDs were rechecked. A root-owned one-off rollout command is installed at
`/usr/local/sbin/kyrion-update-0eb44f6`; its read-only precheck passed. The
operator was given `sudo python3 /usr/local/sbin/kyrion-update-0eb44f6 --activate`.
It creates a protected, quiesced recovery set, rehearses a fresh restore with
original keys in an isolated network namespace, compares original data
projections, and only then activates pinned images. It preserves the existing
environment/TLS configuration, adds Knowledge persistence and recreates the
scoped Caddy proxy (currently unhealthy with healthcheck fork exhaustion).
No activation is claimed by preparing or checking this command; await its
`UPDATE_OK` output and subsequent independent verification. Its exact local
operator source is retained under the ignored
`.run/dev-recovery/pi-update-20261106/activate.py`.

Date: 2026-11-02. Source: `0eb44f6c3b70a6a6b10b99ab9a141cfd5d31ec0f`
plus the Dockerfile and secret-file loader fixes in this checkout.

## Running development stack

Docker Desktop initially failed its WSL integration startup. A targeted Desktop
restart recovered the existing engine and containers. PostgreSQL completed crash
recovery without data deletion or container replacement. Web completed its cold
compilation/cache compaction. Chatterbox completed dependency loading, weight
loading and warmup without changing its model or voice.

All seven checks in `node infrastructure/dev-stack.mjs status` passed:
PostgreSQL, Web, Core, AI, Ollama, STT and TTS. A subsequent normal `start`
completed successfully and reused the ready services.

Core was started through `Start-CoreLan.ps1` using the existing V39 pin and
firewall guards. Its migration gate reported 39 matching migrations, no pending
migrations and no active Calendar leases. The primary checkout's V41 JAR was
built for verification but was not selected for the live Windows database.

The actual Pi probe confirmed DNS, TCP8080, Core health, unauthenticated device
denial and active Gateway/Voice/Spotify/media units. The installed Voice client
opened an authenticated session, received valid 24-kHz greeting audio and closed
the session. This did not open the microphone, play audio or establish fresh
Gateway enrollment/heartbeat acceptance.

## Pi candidate and isolated rehearsal

The existing Pi platform remains on `pi-20260905t140134z`, schema V30. Its Core
health and HTTPS login returned successfully. The `.local` name did not resolve
from this host; SSH used the configured reserved address with strict checking
against the existing `kyrion-node.local` host key. The HTTPS diagnostic used an
explicit local name/address mapping and skipped certificate trust verification;
it does not establish client certificate trust or repaired DNS.

Candidate images were built natively on ARM64:

- `kyrion/web:0eb44f6`
- `kyrion/core:0eb44f6-deployfix`

Two deployment defects were corrected before activation:

- Normalize CRLF in `gradlew` inside the Core Docker build before execution.
- Resolve only `KYRION_DATABASE_PASSWORD_FILE` as a text secret. Credential,
  audit and bootstrap `_FILE` settings remain paths owned by their existing
  components; unrelated environment file settings are ignored.

A protected preliminary Pi database dump was restored into a separate PostgreSQL
container with `--network none` and no published ports. All 30 installed
migration checksums match the candidate source. The fixed Core ran in that
isolated network namespace using ephemeral test keys and applied V31–V41;
Core health returned `UP`. This is database/schema startup evidence, not proof
of production key restoration, audit integrity or external integration behavior.
The original Pi database and keys were not replaced.

The new Web image returned HTTP200 for `/login` in the same isolated namespace;
Core rejected an unauthenticated device read with HTTP401. SQL confirmed 41
successful migration entries. The three rehearsal containers were then stopped;
their isolated database and the private source dump were retained.

Staging, private dump and build logs are in the owner-only Pi directory
`/home/flodinho/kyrion-update-0eb44f6`. The original dump SHA256 is
`49c53863472dea52632515e1771db18fd21337796801f03fb0df2569c520be5a`.
It was taken while the original platform was running and is preliminary
rehearsal material, not the final quiesced full recovery set.

## Verification and remaining activation

The full Core suite passed: **328 tests, zero failures/errors/skips**. `bootJar`,
the new secret-loader regression tests, both native ARM64 image builds and
`git diff --check` passed. No separate Core formatter/linter task is configured.
Web's container build included its TypeScript and production build checks;
no new Web unit/lint run is claimed because Web source was unchanged.

**Production Pi activation is not complete.** The SSH account cannot read the
root-only platform environment and `sudo -n` requires a password. An operator
access question is pending. Before switching the existing platform, retain its
image/configuration pins, quiesce its writers, and back up the real database,
original keys and relevant persistent documents together. Preserve the installed
environment, TLS/radio data and enrollments. Add the current Knowledge storage
mount/configuration as needed; do not simply replace the original Compose file
or reuse the first-install script. Verify the real-key application, schema V41,
HTTPS and authenticated reads after activation. An old image is not a database
rollback after V41. See `docs/v40-rollout.md` for the recovery boundary.

The unrelated modified Calendar/HA recovery worktree was preserved.
