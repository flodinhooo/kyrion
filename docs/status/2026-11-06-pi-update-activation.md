# Pi platform update activated

Later continuation: [local hostname recovery](2026-11-06-local-web-name-recovery.md)
restored ordinary DNS/mDNS and verified Windows HTTPS access using
`https://kyrion-node.local`; the earlier DNS limitation below is historical.

Date: 2026-11-06. Source: `0eb44f6` plus the previously tested Core Docker/secret
loader deployment fixes. The unrelated Calendar/HA worktree and other handoff
documents were preserved.

## Active runtime

- Core: `kyrion/core:0eb44f6-deployfix`, image
  `sha256:f7f4038145b69714a15af5b6ed03ae2a8469937d7603a0beab416a9df8604c04`.
- Web: `kyrion/web:0eb44f6`, image
  `sha256:77ccb71fa8bf63d390baca20cc707e2697550308c2b20e80117d5b476ea0e281`.
- All 41 Flyway migrations successful. Core, Web, PostgreSQL and Caddy healthy.
- A fresh Gateway heartbeat was observed in the Pi database after activation.
- The seven Windows development stack probes all passed, including TTS after
  its cold dependency/model/reference initialization.

HTTPS `/login` returned HTTP200 from Windows at `https://192.168.1.116` using
normal certificate verification, without a CA override or insecure flag.
Hostname access also returned200 when supplied its explicit reserved address;
ordinary `.local` name resolution on this Windows host remains unavailable.

Caddy's existing certificate and private key were retained. Its checked-in and
installed configuration now use `default_sni kyrion-node.local` to select that
certificate for IP clients that do not send SNI. See the
[Caddy default SNI documentation](https://caddyserver.com/docs/caddyfile/options#default-sni).
The configuration passed validation in the installed Caddy runtime before the
scoped proxy restart. Only the existing Pi address and hostname are served.

## Recovery and data preservation

The operator initially ran the prepared command. Its overly strict audit table
count comparison rejected the legitimate new `core.started` event in the
isolated rehearsal. Before any production migration, it restarted the original
V30 platform. Investigation found one appended startup event; every other
checked table matched. The guard was corrected to hash all original audit IDs
and columns, allowing new events while still rejecting historical deletion or
mutation. An isolated test passed for preserved history and rejected a deliberate
historical mutation. Diagnostic containers were removed afterward.

The authorized retry completed with `UPDATE_OK`. Core/Web writers were stopped
for the final database dump. Configuration, TLS and original 32-byte audit and
credential keys were retained in a protected recovery set. The dump checksum was
checked before restoring into a new network-isolated PostgreSQL container.
Original data projections matched after restore and after V31–V41. The new
Core started against the restored database with the original keys mounted read
only. The same preservation checks and key hashes passed after live activation;
unauthenticated device access returned401. Temporary rehearsal containers were
removed. These checks do not claim physical device actions or full audit-chain
certification.

Recovery set:
`/var/backups/kyrion/update-20261106T101135Z-3322d789`.
It includes the protected manifest, SQL dump, original configuration/keys and
successful result. The earlier failed-attempt recovery set is also retained.

The installed Compose entry point remains `/etc/kyrion/platform/compose.yml`.
Original environment placeholders, platform.env, database storage, TLS/radio
data and enrollment credentials were preserved. Images are explicitly pinned;
Knowledge now has its own persistent directory. Parsed effective configuration
was compared before retaining the original YAML interpolation. Only the scoped
platform applications/proxy were restarted, not other Pi integrations or the
Windows/WSL host. Do not start a V30 binary against the V41 database; rollback
requires deliberate restoration/reconciliation using the retained recovery set.

An additional off-Pi archive export to the protected Windows operator directory
was attempted but rejected by automatic approval review because this payload
includes private data, credentials and keys and export to that destination had
not been explicitly authorized. The command was not executed and no export is
claimed. The backup remains on the Pi pending explicit export approval.

## Verification boundaries

The prior source verification remains 328 Core tests, zero failures/errors/skips,
plus both native ARM64 image builds. Those suites were not redundantly rerun for
the operator comparison correction. This activation added live original-key
restore/migration and data-projection checks, positive/negative audit comparison
checks, native image/health checks, Caddy validation, certificate-verified Windows
HTTPS access and all seven local readiness probes. `git diff --check` passed.
Physical voice/device acceptance and live cloud provider acceptance were not run.
