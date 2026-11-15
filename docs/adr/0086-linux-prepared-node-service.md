# ADR 0086: Prepared-node boot service using the installer journal

Status: Accepted for implementation; operating-system acceptance tracked separately

## Decision

Use the existing installer `Installation`, durable journal, target lock and
machine binding for a `linux-prepared-node` deployment profile. Core remains the
only account, Space, pairing and task authority. Node maintenance must not enter
Core database, Compose, backup or update adapters accidentally.

Install the existing frozen installer as an immutable root-owned worker, with a
dedicated non-login system account per deployment. Enrollment and background
execution run as that account; neither receives root authority. Only the agent
directory is writable. Private credentials stay owned by this account. Persist
account-creation intent before the operation and verify exact UID/GID/home/shell
on resume. Preserve the account and credentials when software is removed without
data deletion, preventing accidental UID reuse.

Use a system systemd service, not a login service: bounded restart attempts,
control-group termination, no privileges/capabilities, read-only system paths,
private temporary files/devices and explicit writable agent directory. This
initial service profile supports existing network integration operations, not
direct microphone/USB access. Hardware access needs a separate reviewed policy.
Service activation and successful Core communication are reported separately.
Permission leases from ADR 0085 remain mandatory. Repeated installation must
preserve the existing node identity and reject a conflicting enrollment request.

Unit publication reuses the existing journal-before-publication operation. Only
exact recorded unit/worker content can be repaired or removed. Removal does not
revoke the Core identity: authorized device removal is a separate existing Core
operation. No task migration or cross-device exclusivity is implied.

For this profile, the existing journal's `configuration.manifestSha256` records
the SHA-256 of the executing frozen worker, read through `/proc/self/exe` before
the first journal publication. An interrupted installation cannot silently switch
to another worker. This is local deployment intent, not a signed component-release
manifest or a substitute for installer distribution authenticity. Core release
and update adapters reject this profile; node update integration remains separate
source work under the binding installer scope.

Official references checked for this implementation:
[systemd execution isolation](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html)
and [service restart behavior](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html).
Filesystem isolation does not itself prevent network or Unix-socket access;
Core authorization and protocol validation remain necessary.
