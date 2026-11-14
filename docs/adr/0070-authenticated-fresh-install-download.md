# ADR 0070: Authenticated fresh-install download

Status: Accepted for implementation, 2026-11-14.

The downloaded installer must obtain a compatible published platform bundle
without asking end users to assemble runtime archives or supply a signing key.
Reuse the embedded public release channel, Ed25519 index verification, exact
manifest digest, bounded resumable artifact downloader and existing provisioning.
No public release or production key is created by this change.

A fresh installation has no source database schema. Validate the same complete
release-index contract as updates, selecting by platform, minimum installer,
supported target schema and API; do not fabricate a source-schema migration.
An older supported installer may select a newer compatible published version.

Authenticate small metadata first and show release, exact artifact bytes,
components, release notes, destination and subsequent system-change consent.
Only explicit approval permits large downloads. Use a protected sibling cache,
bound to the target path and separate from the installation journal. Preserve
known partial files for resumption; reject unexplained files and changed content.
Never overwrite user data or silently replace an already selected resume release.

The signed index is the manifest's authority. Carry an explicit typed authority
through review, private native staging and extraction, rechecking its signed
proof against the embedded trust on each boundary. Never invent a detached
manifest signature or trust a downloaded public key. Manual independently
trusted detached-signature bundles remain supported. A cache copy of a public
trust store is not itself a new trust anchor. Offline cached continuation is
allowed only while the embedded signing key remains valid. Rotation remains
the existing operator-authorized trust procedure, not network trust adoption.

Tests must distinguish actual crypto/files/download handling from injected HTTP,
runtime provisioning and OS acceptance. Development builds without an embedded
channel remain explicit, unavailable for this automatic path, and unpublished.
