# ADR 0085: Fail-closed task permissions in the prepared agent runtime

Status: Accepted for implementation

## Decision

The existing Core gateway identity authenticates a device-scoped task-policy
endpoint. The existing prepared agent obtains a short-lived in-memory permission
lease before polling integration commands or forwarding local integration events.
Unknown policies, expired leases, failed transport or revoked credentials remove
local authorization. Core still validates every command/event against current
Space, user and device authority; cached device permissions never replace Core.

Use monotonic local expiry, bounded request deadlines and bounded reconnect
backoff. A prepared runtime does not silently fall back to legacy authority when
the policy endpoint is missing. Legacy, independently configured agent modes
retain their existing behavior. Hardware/service observations are scoped to the
permitted tasks. Task permission does not activate a microphone or install a
controller, runtime or operating-system service.

Linux expiry uses the suspend-aware `CLOCK_BOOTTIME`, so standby cannot extend a
cached grant. The fallback on other client-test platforms is the monotonic clock;
this does not establish Windows prepared-runtime support. See the official
[Python clock documentation](https://docs.python.org/3.12/library/time.html#time.CLOCK_BOOTTIME).

The running agent reports its runtime version in validated health metadata.
Enrollment identity fields stay immutable for safe acknowledgement after a lost
response. Displaying a newer runtime therefore does not invalidate the original
enrollment retry. The agent source version advances to 0.2.0; this is not a public
release or a trigger for installed-device updates. Existing snapshot-based update
recovery remains required; additive stored telemetry does not authorize arbitrary
code-only downgrades.

This lease limits local agent activity. It is not an exclusive task-ownership
lease, a central-writer migration mechanism or a claim that already delivered
physical commands can be recalled. Those handoff requirements remain separate
source work under the existing Core/restore authority.
