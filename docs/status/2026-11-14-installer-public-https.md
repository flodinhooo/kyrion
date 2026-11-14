# Public HTTPS bootstrap for targets without a system CA store

The complete installer assignment remains open. This checkpoint closes the early
public TLS bootstrap gap identified in the Linux runtime checkpoint, without
changing pinned local Core TLS or the signed release/model trust boundaries.

ADR 0073 records the reviewed data-only dependency: unchanged Certifi 2026.10.23
Mozilla CA data and MPL-2.0 license, with wheel and extracted-data SHA-256 pins.
Public release/model metadata and artifact transports use OS trust first. Explicit
certificate settings and existing stores remain authoritative. Only absent OS
trust permits loading the bundled data; certificate/hostname errors are never
retried with weaker verification. No OS trust store is modified.

Both package formats include the public resources. Native builds execute a
capabilities probe and reject missing/tampered resources or disabled verification.
The capabilities report distinguishes resource/policy observations from an actual
connection test. DE/EN errors explain repair without disabling TLS.

## Developer evidence

Eight focused resource/context tests plus actual loopback HTTPS chain/range/hash
tests and a real hostname-mismatch rejection cover the shared transport. Tests
inject missing OS stores only where explicitly stated. The complete suites and
their final counts are recorded in the requirements matrix.

Actual minimal Debian 13 AMD64 chroot evidence:
`build/isolated-linux/public-https-report.json`, owned root
`/work/crypto-clean-fixtures/e33562814599448ead5ada2bfb0f99ed`.
Official OCI manifest and layer digests are retained in that report. Python was
installed without ca-certificates; the actual default context had zero roots.
Ordinary HTTPS rejected the public server certificate. The installer transport
downloaded the official versioned PyPI metadata with mandatory TLS verification.
The frozen Linux worker also executed in that root and reported the same verified
bundled trust policy. This is source HTTPS plus native resource/context execution,
**not a native full-download journey or acceptance of unsigned release metadata**.
The manual Linux workflow prepares the same test; it has not been dispatched.

Native developer artifacts `.20261114.9` in `build/native-installer/`:

- Windows AMD64 EXE: 12,725,452 bytes, SHA-256
  `21d4c5741538215d85888edf4801c6a798e32298c12fa7bd2f936b416ddd0f58`.
- Linux AMD64 archive: 14,531,871 bytes; exact SHA-256 is in its adjacent JSON.
  Executable tested in the CA-free root: SHA-256
  `67558ff01ce0e6d77456e44121cf9e1231b6594c65cc91df45d0063dedf97324`.

Version/inventory/channel/public-CA probes and all raw package source hashes were
checked on both builds. They are unsigned, unpublished, have no productive feed,
and explicitly remain `platformInstallationAccepted: false`. No productive
installation, account, release or device was changed. Bare-target restore/runtime
repair and the other open matrix requirements remain separate source work.
