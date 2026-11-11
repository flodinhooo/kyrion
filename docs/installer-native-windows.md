# Native Windows runtime bundle (development)

This is the ADR 0049 runtime payload contract, not completed Windows installer
support. `native_bundle.py` authenticates and extracts public application/runtime
files; activation, privileged ACL preparation, service/task installation and
maintenance dispatch remain separate, unfinished requirements (matrix R20).

## Build and trust

`release/build-windows-bundle.py --profile <clean-profile> --metadata <json>
--output <new-directory>` produces `manifest.json` and
`kyrion-windows-amd64.zip`. It never downloads dependencies or publishes a release.
The profile contains Windows-built standalone Web assets, existing Core/parser
JARs and dedicated Java 21, Node 22, PostgreSQL 17 and Caddy runtimes. Never copy
`.env`, a developer checkout, links, private keys or personal runtime data into
that profile. Include original licenses/notices in `licenses/<component>.txt`.
Kyrion currently has no selected repository license: its development metadata
uses `LicenseRef-Kyrion-All-Rights-Reserved` and a null license URL, without
inventing redistribution permission.

The schema-2 manifest records exact component versions, HTTPS source/license
metadata, API/schema/PostgreSQL-major compatibility, archive size/hash and every
file size/hash. The builder validates its completed archive before writing the
new output directory. Signing is a separate release-authority step, using the
existing detached Ed25519 `manifest.sig` contract. An independently trusted
public key is required; a key included beside a download is not itself a trust
anchor. Production trust distribution/signing remains outstanding.

Signature verification returns the exact verified manifest bytes. Review and
provisioning bind their digest to those bytes, rather than reopening mutable
metadata after signature verification. Linux image input is copied into the
owned installation's private staging area and rechecked before Docker receives
it; source/download paths are never given to Docker after review.

## Extraction and resumption

`native_bundle.unpack(bundle, trusted_key, destination)` validates all input
before destination mutation, takes the existing cross-platform exclusive
installation lock and refuses an unowned destination. It bounds metadata,
archive expansion, file count and per-file size. It rejects path traversal,
Windows case aliases/reserved names, private configuration, symlinks and unknown
archive entries; PE executables/libraries must be AMD64. It never executes them.

The owned root receipt binds destination and manifest hash. Each member is
written exclusively, hashed, fsynced and promoted with an exclusive hard link.
Repeated runs recheck every existing file and refuse altered content. Partial
public files and interrupted atomic-journal temporaries are preserved outside
the application tree and never adopted as configuration or secrets. Receipt
format 2 uses a compact informational progress count; validated format-1 lists
migrate without weakening file checks. `complete` is set only after every file
passes. Return values explicitly report `runtimeActivated: false`.

## Developer verification

`tests/test_native_bundle.py` uses signed synthetic ZIP/PE bytes without launching
an executable. It covers strict schema/paths, real signatures, tampering,
interruption/resumption, legacy receipt migration, exclusive locking and build
output preservation. These are not Windows service acceptance tests.

`tests/integration/verify-native-windows.py` additionally runs the real verified
native payload, with a fresh synthetic database and random loopback ports. It
checks Core migrations/owner/Space, trusted TLS Web, and local login after
Core/database process restart. It creates no services or scheduled tasks and
cleans up only its own processes/data. It requires Windows, the prepared signed
development bundle, its independently supplied test public key, and OpenSSL:

```powershell
python infrastructure/installer-v1/tests/integration/verify-native-windows.py `
  --bundle <bundle> --key <trusted-test-public.pem> --payload <owned-payload> `
  --work-parent <existing-private-development-directory> --report <report.json>
```

This process-level fixture is not network-isolated and establishes neither
machine boot before login nor the intended Local Service/task-SID ACLs. No
published consumer support or public artifact availability follows from it.
