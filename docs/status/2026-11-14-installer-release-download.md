# Authenticated fresh-install acquisition, 2026-11-14

This continues the full installer assignment, not a user acceptance handoff.
ADR 0070 records the authority boundary. `install_download.py` obtains the
platform bundle through the existing build-bound channel and resumable HTTPS
downloader. `release_policy.fresh_release` validates the complete existing index
contract without pretending that a fresh target has an installed source schema.
Selection enforces the installer minimum, actual platform, API 1 and the currently
implemented target schema 49. It does not promise support for future schemas.

The terminal flow uses this path when no independently trusted manual key is
provided. Signed metadata is checked before artifact paths or sizes are used.
Download consent shows release, component versions, exact bytes, notes and native
component license/source metadata. Separate installation consent is retained.
Progress reports observed transferred bytes. Disk checks reserve the remaining
download, private installation copy, known native expansion and 12 GiB baseline.

The private sibling cache is target-bound. Complete metadata is published as a
directory before downloads start; interrupted metadata preparation leaves a
private unadopted sibling, preserved for diagnosis. The next attempt can prepare
again. Interrupted artifact downloads resume using verified HTTPS Range handling.
Unknown files, changed manifests, altered proofs and expired authority fail
closed. Existing caches continue their exact selected release rather than
silently selecting another version mid-installation. Complete cached inputs need
no network request while their signed proof remains valid. Cache and abandoned
preparation directories are not automatically deleted.

`IndexAuthority` carries signed-index authority through shared bundle review,
private native staging and extraction. Each boundary checks the proof against
the embedded channel. Downloaded public keys are never trusted; no manifest
signature is invented. Manual detached-signature bundles keep their existing
path. This change creates no account/Space/integration authority.

## Verification

Full suites pass: **365 Windows tests, three skips**, and **367 isolated Linux
tests, 16 skips**. Ruff lint passes. Seven new integration tests use actual
loopback TLS with a test CA, real Ed25519 signatures, streaming download/range
resumption, filesystem journals and native ZIP validation/extraction. OS
administrator/ACL and free-space observations are explicitly injected; runtime
services are not installed. Two policy regressions cover fresh-schema selection
and complete index validation. Existing update/detached-signature tests pass.

Reports: `build/installer-tests-20261114-install-download-final.txt` and
`build/isolated-linux/test-report-current.txt`. Native builds are recorded
separately after packaging. No productive feed/signing key is generated and no
release or CI workflow is published/dispatched. Full native elevated Windows
setup, real application boot, distributed installation and remaining product
journeys retain their implementation/acceptance entries in the matrix.

## Operator setup and continuation

Build the standalone installer on the target platform using
`release/build-native.py --version VERSION --channel REVIEWED_CHANNEL.json --output OUTPUT`.
The existing channel contract requires a real HTTPS signed index and reviewed
release-index/trust-rotation public keys with validity periods. Stable builds
refuse a missing channel. Publish accepted runtime artifacts and their signed
index only through the separately authorized release procedure. The index pins
exact manifest hashes; artifacts use the existing relative manifest-location
contract. Production trust/feed configuration is an operator prerequisite, not
a reason to bypass verification.

On an administrator/root terminal, launch the downloaded installer, select
language and fresh/resume, enter local hostname/address, review and confirm
DOWNLOAD, then review and confirm INSTALL. No manual bundle/key flags are needed
for the embedded-channel path. Without a channel the development binary reports
its unavailability. Source/operator bundles remain usable with
`--bundle DIRECTORY --public-key TRUSTED_KEY.pem`. These are developer/operator
instructions; no partial user test is requested.

Native `.20261114.5` development builds include this source and passed actual
version/channel/inventory smoke execution; every raw source hash matches.
Windows EXE: 12,568,353 bytes, SHA-256
`232536de9356d60f66d401b32a009b61a20f8bbef811f16cf34373fbf1251cbb`.
Linux AMD64 archive: 14,373,717 bytes, SHA-256
`9660abac540e1d40fd4291c8ffe404d61daaa5554651850c5a89a2c43b81ba74`.
Both are in `build/native-installer/` with adjacent JSON metadata and remain
unsigned, unpublished and explicitly `platformInstallationAccepted: false`.
They have no productive embedded channel; configured acquisition is covered by
the isolated signed-channel integration tests above, not a native host install.
