# ADR 0045: downloaded installer owns host setup

Status: accepted for the incremental implementation, 2026-11-11.

## Context

The current fresh installer uses Python, signed OCI bundles and Compose. The
requested Windows/Linux guided product is broader than the released evidence
(there is no accepted public installer). Website identity, local Core identity,
Space membership and integration authority already have distinct owners.

## Decision

Extend `infrastructure/installer-v1` using a bilingual local terminal wizard and
fixed Python orchestration, with no new framework or arbitrary command execution.
The downloaded installer owns host probes, review, image verification, protected
installation state and provisioning. The public website never owns those states.
Core retains accounts, Space, authorization and integrations. The local guided
flow invokes existing bounded Core APIs; passwords/tokens use process stdin and
memory, never shell arguments or installer storage. Do not persist
passwords, provider tokens or application sessions in installer state.

Use an exclusive OS lock and atomic private journal. Resume only the same signed
release and configuration. Track fingerprints of managed files, including secrets,
without including their contents in reports. Fail closed on ambiguous ownership.
Do not adopt existing development/Pi installations. Repair/restore/update modes
remain explicit unavailable operations until their own safe paths exist.

Only candidate Debian 13/64-bit Raspberry Pi OS 13 Compose runtimes may provision.
Windows gets actual read-only inventory now; no Docker Desktop login startup is
called system startup. Broader Windows host/service support requires a separate
tested runtime decision. Later nodes enroll through Core-authenticated contracts;
this installer never claims arbitrary LAN machines can be remotely provisioned.

## Consequences

The first deliverable improves executable fresh setup and truthful diagnostics;
it does not certify a complete consumer product. Existing Core APIs supply
owner/HOME Space, optional identity linking and HA probe/import; the existing
local UI retains those administrative functions. Broader onboarding remains open.
Each pending product requirement stays visible in `docs/guided-installer.md`.
No fabricated update, pairing, model-download or hardware success is permitted.
