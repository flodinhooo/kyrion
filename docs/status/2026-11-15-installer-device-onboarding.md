# Device management inside guided onboarding

The complete assignment remains open. This adds the existing Core-owned device
management to the downloaded installer's normal linked-account/Space journey.
It is not a replacement device registry or complete distributed task placement.

After local access/Space/recovery setup, `SINGLE` continues with the installed
central components; `DEVICES` opens the existing authenticated management and
one-use pairing flow; `LATER` defers the optional step. Core is re-read before
the choice is marked reviewed. A transfer awaiting redemption is not an enrolled
device. Existing paired devices are retained when selecting the simple path.
Interrupted individual setup remains `in-progress` in the installation journal.
Users lacking gateway read permission can continue other setup unchanged.

The bilingual guidance explains target-side installer execution, intermittent
availability and separate task/runtime activation. It does not promise deployed
AI, recording, remote shell installation or a cloud fallback. The obsolete setup
handoff text claiming optional account linking and read-only Home Assistant was
corrected to match the existing implemented paths.

## Evidence

- Installer suites passed: 532 reported Windows tests and 551 reported Linux
  tests, twenty platform skips each. New scenarios cover deferral without gateway
  access, existing-device preservation, permission limits, individual management,
  interruption and invalid selection. Ruff and changed-file formatting pass.
- The actual Linux Compose/Core/PG/Web/Caddy fixture now enters pairing through
  the new individual setup choice. It passed actual code issuance after reviewed
  proxy extension, interruption/resume and outage recovery. No successful Core or
  proxy response was simulated. Report:
  `build/isolated-linux/agent-ingress-compose-report.json`.
- A fixed public source snapshot passed actual Windows Core/PG/Web/Caddy process
  acceptance with the linked-account fixture. Guided setup selected SINGLE with
  no hardware or AI; BUSINESS membership, role denial, invitations, proof expiry,
  local identity reuse and offline login after process restart passed. Core JAR
  SHA-256: `998ddd7a7e88d99a052ada709882fcf83f3e6022aec149749c45ad1853057f00`.
  Report: `build/linked-device-windows-profile-report.json`.

The Windows process fixture used an existing public runtime profile whose entire
file set, sizes and hashes were verified against the authenticated test manifest.
Its explicit `--verified-profile` path avoids redundant extraction for application
tests and does not claim extraction, service registration, virtual-account ACL,
network-namespace or cold-boot acceptance. The initial redundant extraction test
timed out after fifteen minutes, preserving its partial receipt; it is not counted
as passing. A separate early process attempt mixed changing source modules and
failed; the passing repeat ran from a fixed source snapshot.

Native Windows ingress/service work is continuing separately under ADR 0089.
Full placement/dependency validation, exclusive handoff, prepared Windows targets,
node updates/backups and the remaining requirements ledger are still open. No
artifact was published and no user partial test or acceptance is requested.
