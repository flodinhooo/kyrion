# Device management and restricted agent transport checkpoint

The complete installer assignment remains open. This checkpoint is developer
evidence, not a request for user acceptance or a product release.

## Implemented behavior

- Core schema 51 extends existing gateway identities, Space isolation and RBAC.
  Revision-bound edits change names and expected availability independently of
  heartbeats. Concurrent administrative writes cannot silently overwrite changes.
- Durable revocation invalidates gateway access and voice identities explicitly
  bootstrapped from that gateway. Open linked dialogue sessions close and pending
  or running commands fail. History and user data are retained. Already delivered
  physical actions cannot be recalled.
- Integration and voice task policies gate existing command ingress/dispatch,
  integration synchronization, event ingress and linked voice authentication.
  Protocol-2 prepared enrollments start with no task permissions. Legacy nodes
  keep their established authority until explicitly configured. Unknown task
  kinds are rejected. Task permissions do not install software or prove readiness.
- The downloaded installer's bilingual `--devices` maintenance path uses the
  established linked login and authoritative Core state. Changes and removal
  require review; errors do not produce success displays. Responses are escaped
  before terminal output. No competing local device registry is introduced.
- New native and Compose configurations provide enumerated agent protocol routes
  through their existing TLS listener. Immediate peers must be local; forwarded
  headers cannot grant local status. Native upstream TLS validation stays enabled.
  Owner APIs and unknown routes are not forwarded to Core by this transport.
- Restore/update capabilities and the isolated migration operator explicitly
  recognize schema 51. Earlier reviewed schemas 49 and 50 remain recognized;
  unknown future schemas are rejected.

## Verification

The initial metadata implementation passed 50 focused Core tests and actual
Core/PostgreSQL/TLS/agent-process edit, revocation and restart checks. Expanded task
policies passed the full 216-test Core security/gateway suite (one existing skip),
including real PostgreSQL, authorization, migration rehearsals and concurrent task
writes, concurrent heartbeats without lock-upgrade deadlocks, and replacement of
revoked gateways and their same-hostname voice identities without reviving old
credentials. The final Core artifact is
`core-device-management-3809d1afe19e.jar`, SHA-256
`3809d1afe19e66b812a41973c39045f5133ae40716c93cd8e118d02ab7081cfd`.

Installer suite after task-policy, proxy and repair integration: 497 Windows tests
(nine skips), and 505 isolated Linux tests (twenty skips); Ruff passed. Proxy
repair preserves the recorded old or new configuration without silently enabling
new routes. The actual Windows Caddy process test
uses synthetic local TLS upstreams, verifies route separation and rejects the
wrong upstream certificate. It does not claim SCM startup or a real nonlocal
Windows source-address test. The corresponding isolated Linux test supports a
real nonlocal source address plus forged forwarding headers; that test passed.

Native development artifacts `0.0.0-dev.20261115.1` were built and smoke-tested on
their actual platforms. Both recorded source snapshots match the packaged source;
embedded version/channel/public-CA checks passed. They are unsigned, unpublished,
and do not establish complete installation or service acceptance:

| Platform | Bytes | SHA-256 |
| --- | ---: | --- |
| Windows AMD64 | 12,781,162 | `dfae82aaf8f43a50378dcadad05b88a0e86509cecc9ffc56705c0745d784f7cc` |
| Linux AMD64 | 14,587,705 | `b54f5b0bb2e11a1f9fd7b6b56ea899688df123132cf6695e5b5175c5e5ea0681` |

The installer does not embed the Core application JAR. Reviewed runtime releases
remain separate. Core schema-51 process fixtures additionally exercised actual
encrypted backup, inactive verification, restore, offline restart login, and a
51-to-synthetic-52 update/recovery transaction. A synthetic next-schema sentinel
is not a published or generally supported schema 52.

Executable fixtures:

```text
python -m unittest discover -s infrastructure/installer-v1/tests
python -m unittest discover -s infrastructure/dev -p test_core_schema_migration.py
services/core/gradlew.bat -p services/core test --tests dev.kyrion.core.security.GatewayAuthorityIntegrationTest
```

`tests/integration/verify-agent-enrollment.py` exercises actual Core, PostgreSQL,
verified TLS and separate agent processes, with supplied terminal choices and one
explicit lost-acknowledgement fault injection. `verify-agent-proxy.py` runs an
integrity-checked Caddy executable with synthetic TLS upstreams. Its optional
`--public-peer` requires a caller-prepared isolated namespace address. Neither
fixture starts recording or controls household devices. The existing application
restore/update fixtures exercise actual databases and processes; operating-system
service acceptance is a separate boundary.

## Remaining implementation, not external blockers

Full installer-driven node deployment and pairing, Windows prepared-agent storage,
deployed agent services, distributed AI transport, exclusive task handoff/leases,
the local Web management interface, and the remaining full-scope matrix entries
are not complete. Existing installed proxy configuration still needs a reviewed
extension transaction. Task permissions alone do not complete requirements R23,
R25-R29. Missing source work is not attributed to missing hardware or signing keys.

Windows SCM/cold-boot and physical ARM64 acceptance remain separate target-system
limits. No product release, public download, productive deployment or household
action has occurred.
