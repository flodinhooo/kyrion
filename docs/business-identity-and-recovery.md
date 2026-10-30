# Business identity, policy and host-local OWNER recovery

## Guarantees and deployment boundary

HOME and BUSINESS are distinct local Spaces and account identities. Accounts cannot
move between Spaces. This milestone retains the single-Space startup guard. It
does not certify managed multi-tenant hosting, all providers or parallel knowledge
work. [Tenant audit](spaces-tenant-audit.md) records coverage and explicit blockers.

No website, portal, Kyrion-operated cloud, SSO or privileged support operator is
required. SMTP is an optional instance-controlled delivery provider. With no SMTP,
existing HOME functionality and Business policy OFF remain available locally.
Missing SMTP never manufactures mailbox proof or silently enables strict policy.

## Three distinct proofs

1. SMTP mailbox proof: an authenticated account requests a code, receives it at
   that address, and submits it on its instance. For enrollment, the code binds
   to the invitation, Space and recipient before the account exists.
2. DNS domain-control proof: an OWNER publishes a generated TXT challenge in DNS;
   Core queries DNS and compares the complete record to the stored challenge hash.
3. Local administrative attestation: the host administrator independently checks
   identity and records an attestation with host recovery material and the current
   OWNER password. It is labelled `LOCALLY_ATTESTED`, never `VERIFIED`, and cannot
   satisfy strict SMTP/domain policy.

An email address is never proof of domain ownership. Local-part case is preserved;
ASCII mailbox syntax is supported, including plus tags. Internationalized local
parts, quoted mailboxes, display-name syntax and SMTPUTF8 are deliberately unsupported.
Domains normalize through IDNA/STD3 ASCII and lowercase; trailing root dots are
removed. Wildcards, URLs, IP literals, empty labels and invalid labels are rejected.
Domain matching is exact. `company.ch` does not authorize `subsidiary.company.ch`.

## Mailbox workflow

Settings → Identity and recovery shows the account's own state. `POST
/v1/identity/email` sets a pending address and sends a 256-bit code. Only SHA-256
hashes persist. Codes expire in 15 minutes, are one-use, and are superseded on
resend. Resend is bounded to one per minute and five per hour per account or
invitation. Invalid verification attempts use bounded per-account backoff.

`POST /v1/identity/email/verify` consumes the code transactionally. Existing verified
addresses remain authoritative until a replacement is proved. A profile update
cannot set verification state. Pending tokens, users, invitations and addresses
are scoped server-side; code replay and concurrent verification have one winner.

Signup can request email proof using its invitation and address at `POST
/v1/auth/registration-email`. Every syntactically valid request gets the same 202
response, including unknown invitations, policy denial and unavailable SMTP.
No unauthenticated response returns a token or reveals account/Space existence.
Registration supplies `email` and `emailProof` with existing credentials and
`invitationCode`. Creation, role assignment and consumption of both proofs share
one transaction. Legacy registration remains unchanged while policy is OFF and
there is no email-bound invitation.

Authenticated Web mutations retain the existing CSRF/session proxy. Tokens are
entered transiently, never persisted in browser localStorage. Audit events contain
operation/actor/Space/correlation identifiers, not addresses, codes or credentials.

## SMTP configuration

See `infrastructure/business-identity.env.example`. Configure process environment
or equivalent protected deployment secrets:

```text
KYRION_IDENTITY_SMTP_HOST=mail.example.invalid
KYRION_IDENTITY_SMTP_PORT=587
KYRION_IDENTITY_SMTP_USERNAME=replace-with-username
KYRION_IDENTITY_SMTP_PASSWORD=replace-with-private-credential
KYRION_IDENTITY_SMTP_FROM=verification@example.invalid
```

The existing secret-file processor also supports
`KYRION_IDENTITY_SMTP_PASSWORD_FILE`. Do not set an empty HOST if the file variable
points to a missing file: the existing processor validates every `_FILE` setting.
STARTTLS is mandatory, certificates and server identity are checked, connection/
read/write timeouts are bounded, and SMTP debugging is disabled. There is no
plaintext fallback or log/HTTP token-delivery mode. Port 465 implicit TLS and
display-name FROM values are not implemented. Use a STARTTLS-capable relay.

The Spring Mail starter is the one added application dependency; it supplies a
maintained SMTP/TLS implementation instead of custom protocol/credential code.
Loopback transport tests verify that missing STARTTLS blocks AUTH/message data
and that DNS TXT character strings are correctly decoded. No real SMTP account
or external customer domain was contacted during automated tests; delivery is replaced
by a capturing test transport. Validate your actual relay and certificates before
relying on production verification.

## DNS ownership and policy activation

Only a Business OWNER can create/rotate or check a challenge. The TXT name is
`_kyrion-verification.<domain>`. Its unpredictable value includes the Space UUID.
Challenge hashes expire after 30 minutes and rotate explicitly. Core uses bounded
JNDI DNS queries via the host resolver (or an explicitly configured trusted
`KYRION_IDENTITY_DNS_SERVER=dns://resolver-address/`); TXT character-string segments are joined.
Successful proof is single-use and valid for 30 days. Failed/expired/unrelated
records never mark a domain verified. Previous unexpired proof remains valid while
a fresh challenge is being provisioned.

Trust the host's DNS resolver and its network path. Use a controlled DNSSEC-validating
resolver where available. This implementation does not itself validate DNSSEC or
provide continuous ownership monitoring. A domain can change ownership during the
30-day validity window. Reverify before expiry and after DNS ownership changes.
In strict mode, OWNER can immediately stop new enrollment for a domain by invalidating
its DNS proof after suspected ownership change. This expires its proof and challenge and requires a fresh DNS challenge.
After suspension or expiry new invitations, enrollment and email changes are blocked; existing
verified members retain access, including OWNER policy/recovery operations.

Strict activation explicitly selects the allowlist and confirms revocation of
outstanding invitations. Core requires configured SMTP, current DNS proof for
every selected domain, provisioned recovery, and SMTP-verified allowed email for
every enabled member. Activation cannot exclude an enabled OWNER or ordinary
member. It changes no roles, account passwords or old resource ownership.

Strict invitations must bind a recipient address. Acceptance must prove that exact
mailbox on the same invitation. Email changes are checked at request and completion.
Changing the Space to HOME cannot hide an active strict policy. OWNER can disable
strict policy even when DNS proof expires; disabling is audited. Disabled members
must satisfy current identity policy before reactivation. Local attestation never
bypasses strict mode.

## Host-local recovery

There is **no recovery HTTP endpoint**, master password, remote support grant or
new-owner creation. The CLI does not start Spring, HTTP, scheduling, AI or providers.
It requires an interactive console and refuses redirected input/output. Passwords,
offline codes and sessions are read through hidden console input, never arguments.

Provision recovery as a local setup step after first OWNER creation. The operation
requires the existing OWNER password, installation database credentials and audit
key. A protected per-Space host key stays on the host; the separate offline code is
shown once and must be stored privately away from the host key. Ordinary database
persistence stores only context-bound hashes. Codes bind to the installation UUID,
Space and root OWNER, and expire after a year. Use `rotate` before expiry.

`open` requires both the protected host key and offline code. It consumes the old
code, prints a replacement offline code, and issues a five-minute one-use recovery
session. Store the replacement immediately: it permits retry if the session expires.
`complete` requires the host key, session and a different password of 12–200
characters. It rotates the password/offline code, revokes OWNER sessions and pending
email proofs/invitations, and preserves membership, roles, credentials and data.
Normal login is required afterwards; recovery issues no unrestricted login token.
The CLI verifies the existing Space audit chain with the supplied installation
key before any administrative write. Recovery and failures are sealed in that chain, with the local process
operator identifier and Space. Audit failure rolls back security changes.

`rotate` requires host key and current OWNER password, rotates offline material and
invalidates pending recovery sessions. `attest` additionally requires an explicit
ATTEST confirmation and target member of the same Space, and is unavailable during
strict policy. Never claim local attestation proves mailbox or DNS control.

If both the current password and valid offline recovery material are lost, there
is no bypass. Use an independently protected backup or a separately reviewed local
restoration procedure. Database/audit/host-key administrators remain trusted; no
software can prevent a fully privileged operator modifying its database and keys.
After a backup restore or cloned installation, explicitly rotate recovery material;
database rollback can otherwise restore previously consumed credentials.

## Linux production procedure

Use the release jar and a private operator terminal on the installation host.
Use a maintenance window for recovery, with Core/Web stopped and PostgreSQL still
running, so audit verification sees a consistent chain. Restart normal services
after completion. A failed audit preflight cannot be bypassed by this CLI.
Provision a directory owned by the Core service account with mode 0700; the CLI
creates its key with mode 0600. Set these variables through your protected service
environment, with real paths outside the repository:

```sh
export KYRION_DATABASE_URL='jdbc:postgresql://127.0.0.1:5432/kyrion'
export KYRION_DATABASE_USER='kyrion'
export KYRION_DATABASE_PASSWORD_FILE='/etc/kyrion/secrets/postgres-password'
export KYRION_AUDIT_INTEGRITY_KEY_FILE='/etc/kyrion/secrets/audit-integrity.key'
```

Run as the authorized service/host administrator with Java 21; substitute the actual
Space UUID shown by `/v1/auth/me` and a protected key path:

```sh
java -Dloader.main=dev.kyrion.core.security.LocalSecurityAdmin \
  -cp /opt/kyrion/app.jar org.springframework.boot.loader.launch.PropertiesLauncher \
  provision SPACE_UUID /var/lib/kyrion/recovery/SPACE_UUID.host-key
```

Use the same invocation with `open`, then `complete`, or `rotate`. To record a
separate local attestation, append `MEMBER_UUID member@example.invalid` after
`attest SPACE_UUID HOST_KEY_FILE`. The procedure uses ordinary database transactions
and the existing audit key, not production schema changes. Back up recovery material
privately. Never pipe the command, redirect output, or run it in application logs.

## Docker Compose and installer

The current template runs Core as UID/GID 10001 and uses a read-only root filesystem.
Prepare a host recovery directory owned by that UID/GID with mode 0700 and bind it
read-write **only for the interactive administrative command**. Keep the database
on its private Compose network. From the installation Compose directory:

```sh
docker compose run --rm --no-deps --entrypoint java \
  --volume /var/lib/kyrion/recovery:/run/kyrion-recovery \
  core -Dloader.main=dev.kyrion.core.security.LocalSecurityAdmin \
  -cp /opt/kyrion/app.jar org.springframework.boot.loader.launch.PropertiesLauncher \
  provision SPACE_UUID /run/kyrion-recovery/SPACE_UUID.host-key
```

Compose supplies the existing database password/audit secrets. Use a real TTY;
do not use `-T`. Repeat with `open`/`complete`/`rotate` for later operations. No ports
are published by this administrative container. Do not mount the offline code.
Existing installer templates are preserved. Installer v1 is still planned; its
post-bootstrap operator acceptance must include recovery provisioning and backup.
No automatic installer success or deployment is claimed by this milestone.

## Windows development procedure

Use a private PowerShell terminal and the worktree's built
`services/core/build/libs/kyrion-core-0.1.0-SNAPSHOT.jar`. Export the same database/
audit environment variables using Windows paths. Create a private recovery directory
outside the repository, remove inherited broad grants and grant only your operator
SID (optionally SYSTEM/Administrators). Example, for an explicitly chosen new directory:

```powershell
$recoveryDirectory = 'E:\Kyrion\Data\recovery'
New-Item -ItemType Directory -Path $recoveryDirectory -Force | Out-Null
$operatorSid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
icacls $recoveryDirectory /inheritance:r /grant:r "*$($operatorSid):(OI)(CI)F"
java "-Dloader.main=dev.kyrion.core.security.LocalSecurityAdmin" `
  -cp services/core/build/libs/kyrion-core-0.1.0-SNAPSHOT.jar `
  org.springframework.boot.loader.launch.PropertiesLauncher `
  provision SPACE_UUID "$recoveryDirectory\SPACE_UUID.host-key"
```

The CLI validates the file ACL; broad data-read/write or ACL-owner grants fail closed.
Do not reuse `$HOME`, put secrets in PowerShell history, or pass passwords/codes as
arguments. Run `open`, `complete`, `rotate` with the same protected file. A real
interactive Console is required; IDE output panes and redirected sessions are rejected.
Windows protected-file behavior is automatically tested; real production Docker/Linux
operator acceptance remains an explicit deployment check.
