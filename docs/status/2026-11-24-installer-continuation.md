# Installer continuation: reviewed Space binding

The complete assignment remains open; no partial user acceptance is requested.

## Implemented

ADR 0091 extends the existing enrollment and Space authority. Core atomically
filters one-use code consumption by the optional expected Space, returns its
actual Space and advertises binding protocol 1. Wrong expectations do not consume
a code. Acknowledgement retries also enforce the expected Space and current
Space availability. The owner code response remains compatible with historical
three-field parsers. No schema migration or second identity registry is added.

The existing agent checks compatibility before transmitting a bound code,
persists immutable pending format 2, verifies the actual response and retains the
confirmed Space in AgentConfig. Legacy pending format 1 remains resumable without
silently acquiring a new expectation. The installer forwards the reviewed UUID
through foreground import and Linux service enrollment and refuses old Core
before creating an owner transfer. DE/EN errors explain preservation and retry.

Windows transfer loading/materialization now uses the existing protected native
storage adapter. Native identity uses IsWow64Process2 and the observed NT version,
not environment architecture aliases. See Microsoft's [native architecture API](https://learn.microsoft.com/en-us/windows/win32/api/wow64apiset/nf-wow64apiset-iswow64process2)
and [Python version semantics](https://docs.python.org/3.12/library/sys.html#sys.getwindowsversion).
This does not enable Windows target health, runtime or SCM deployment.

## Verification

- Agent suite: Windows 91 passed / 19 skipped; Linux 89 passed / 21 skipped.
  Includes ten explicit protocol-boundary regression cases and actual Windows
  pending-file continuity after injected lost HTTP acknowledgement.
- Installer suite: Windows 544 passed / 20 skipped; isolated Linux 563 passed /
  25 skipped. Logs: `build/installer-space-binding-tests.txt` and
  `build/isolated-linux/test-report-current.txt`.
- Subsequent targeted Windows pairing suite: 10 tests / one POSIX-only skip;
  actual protected packet import/materialization included. Native health/identity
  suite: five passed / one Linux-only skip. Ruff passes.
- The broad Core security/gateway invocation completed its authorization suites,
  including all 44 GatewayAuthorityIntegrationTest and 11 GatewayServiceTest
  cases. Eight dedicated schema rehearsal tests initially failed because the invocation
  omitted their mandatory immutable artifact environment setting. Repeating only
  those eight with the required immutable artifact and Python runner passed
  (`build/core-space-binding-migration-tests.txt`). Initial runs before Docker startup
  could not connect to the test engine; those are not passing evidence.
- Actual Core/TLS/Windows private enrollment passed from an immutable public
  source snapshot: a rejected wrong-Space claim leaves the same code usable;
  discarding a real successful response resumes with the same node/credential.
  Linked BUSINESS setup, member authorization, no optional equipment, actual
  PostgreSQL/Core process restart and offline linked login also passed. Report:
  `build/space-binding-windows-profile-report.json`. The first run timed out during
  a later PostgreSQL shutdown checkpoint; the bounded 180-second repeat passed.
  No SCM or household actions were used. This verifies an existing authenticated
  public runtime profile, not fresh extraction, service ACLs or cold boot.
- Windows task-lease time now uses native GetTickCount64 (includes sleep and
  hibernation), avoiding extension of a short permission lease while asleep.
  Targeted bound-protocol/runtime suite: 24 passed. Actual suspend/resume hardware
  acceptance is outstanding. See [Windows interrupt-time semantics](https://learn.microsoft.com/en-us/windows/win32/sysinfo/interrupt-time).

Candidate Core artifact: `build/core-space-binding-edbb676b5fd9.jar`, SHA-256
`edbb676b5fd9a4b196b9411e6d0ae1379a1c5a1765b77162da3625d43b133ed0`.
It is private and not published. Historical `.15` native installers do not include
this source batch. No current public release or full Windows device support is
claimed.

## Continuation

Continue Windows health unknown values, scoped
runtime and service deployment, followed by full task dependency/placement and
exclusive handoff. Node backup/update integration and the wider requirement
ledger remain binding. Preserve unrelated `apps/web/tsconfig.json` changes.
