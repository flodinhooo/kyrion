# Guided installer implementation and acceptance

Reviewed 2026-11-11. This is the work record for the downloaded installer;
kyrion.ch is a download/documentation surface, never an installation authority.

The detailed [binding requirement matrix](installer-requirements.md) supersedes
the coarse historical stage table below. Continuing source/test work is recorded
in [the continuation evidence](status/2026-11-11-installer-continuation.md). The
full product scope remains open; no user acceptance is requested for this state.
The later [linked account evidence](status/2026-11-12-installer-identity.md) and
[integration/build evidence](status/2026-11-13-installer-integrations.md) supersede
older planned-only descriptions of those implemented slices. They do not close
distributed enrollment, complete runtime/model/voice setup or installed updates.

Native release builds embed their requested version. Inspect with `--version`;
there is no caller-supplied `--installer-version` override. Build the standalone
installer with `release/build-native.py --version VERSION --output OUTPUT` on
its actual target. On Windows build the service host using
`release/build-native-service-host.py --version VERSION --output SERVICE_OUTPUT`
with the **same** version before profile assembly. Both builders check the
frozen executable's version as well as its real inventory probe. Source and
Python test archives use a development identity and cannot query a stable update
feed by pretending to be a released installer. These builds remain unsigned
development artifacts until the separate release and acceptance gates pass.

## Native maintenance continuation

For an owned native Windows installation, elevated terminal maintenance now
supports `--target C:\ProgramData\Kyrion --backup E:\Backups\kyrion.gpg`.
Choose an existing destination directory and a new output filename. The installer
requests maintenance confirmation and a repeated backup passphrase. The runtime
bundle must include the prepared, manifest-hashed portable GnuPG dependency;
older development bundles without it fail before services are paused. Original
keys/configuration are encrypted, and the passphrase is never a command argument.
This is capture, not full restore or an automatic backup schedule.

`--check-updates --target TARGET --feed FEED --trust-store TRUST_FILE` now
supports both Linux and native Windows. FEED must be the actual signed release
index and TRUST_FILE the reviewed public release trust store; no production
channel is invented here. Native Windows reads its actual database schema with
verified PostgreSQL tools. Stable-channel checks require an actually released
installer build identity; current development artifacts are refused. The default
check only reports a compatible candidate and never installs it. Background
scheduling and update transactions remain open implementation work.

## Inventory and conflicts

* `infrastructure/installer-v1`: Python standard library, shell, signed image
  archives and Compose. The old entrypoint wrote directories before preflight,
  causing its own existing-state checks to fail. It did not start the stack.
* `apps/website`: bilingual independent public site; no released download exists.
  `apps/web`: existing protected owner/Space setup, profile identity linking,
  integration catalog, system diagnostics and recovery entrypoints.
* Core: authoritative local password hashes, bounded authentication attempts,
  persistent sessions, roles, one active Space per installation. Optional RFC8628
  central linking preserves the same local identity. Public central identity is
  not operationally accepted. Selecting arbitrary remote Spaces is not supported.
* Home Assistant: encrypted credentials, bounded selected inventory preview/import,
  room overrides, periodic refresh and owner isolation. Explicit single-entity
  power consent uses the common Core command boundary and state confirmation;
  physical acceptance remains separate. Legacy imports stay read-only.
* AI: existing Ollama and optional cloud adapters/policies. Satellite and STT/TTS
  runtimes exist separately; no release images or turnkey voice provisioning.
* Releases: ARM64 OCI builder, Ed25519 detached manifest verification and protected
  signing workflow. Publishing deliberately disabled. Placeholder has no images.
  No trusted public download channel, key rotation or general updater exists.
* Recovery: scoped PostgreSQL dumps, original-key capture and isolated restore
  tooling. Not a complete portable encrypted backup/restore or schema rollback.

The requested product scope supersedes the old ARM64-only/fresh-only product
plan, but does not make missing Windows, multi-device, multi-Space or HA control
implementations available. These boundaries must change in their existing owners,
not by inventing parallel installer account/device/integration databases.

## Checkable stages

| ID | Outcome | Status / acceptance |
| --- | --- | --- |
| G1 | Inventory, decision and explicit support matrix | Recorded here and ADR 0045 |
| G2 | Strict signed bundle verification; only declared images can load | Implemented; synthetic digest/path/signature regressions |
| G3 | Actual target inventory on Windows/Linux, unknown values explicit | Implemented; read-only Windows probe and unit fixtures |
| G4 | Guided bilingual terminal flow; durable journal; safe fresh install/resume | Implemented for candidate Linux hosts; injected runtime tests, not OS acceptance |
| G5 | Trusted TLS, bounded startup, same Core owner/Space setup; no AI required | Runtime provisioning implemented; real clean-host/image acceptance pending |
| G6 | Windows runtime without sign-in, packaging and platform acceptance | Portable Python archive packager implemented/tested; native Windows runtime, signed distribution and host acceptance open |
| G7 | Core-authorized device pairing/task transfer, offline-safe migration | Open; gateway/satellite enrollment is not a general installation agent |
| G8 | Installer-driven existing identity/Space/recovery and HA selection/control | Partial: existing Core owner/HOME setup, login, RFC8628 link, hardware questionnaire and real HA probe/import wired; recovery, selective import/control and existing remote Space selection open |
| G9 | Signed model catalog, measured recommendations/Ollama/Velora lifecycle | Open; no guessed model metadata or automatic cloud fallback |
| G10 | Signed compatible updates, consistent encrypted backups/restore/repair | Open; fresh installer must refuse these mutations until implemented |
| G11 | Website downloads/help/advice backed by accepted published artifacts | Open; no fake executable download or unpublished release link |

## Support and evidence

| Target | Implemented path | Verification / release status |
| --- | --- | --- |
| Windows x64 | Read-only inventory, existing-state detection | Executed on this Windows host; no native installation or boot-service acceptance |
| Debian 13 ARM64 | Guided Compose fresh install/resume candidate | Unit/contract tests only; no clean-host acceptance |
| Debian 13 x64 | Same candidate path; requires matching AMD64 signed images | Unit/contract tests only; builder/host acceptance pending |
| Raspberry Pi OS 13 ARM64 | Same candidate path | No physical acceptance; not all Raspberry Pis supported |
| Other Linux / Windows ARM / 32-bit | Inventory where available; provisioning refused | Unsupported |

Minimum candidate capacity: 4 GiB RAM, 12 GiB free storage, Python 3.12+,
Docker Engine with Compose v2, OpenSSL and systemd. Capacity is a floor for the
non-AI stack, not an AI performance promise. Additional runtime installation is
never automatic. GPU/VRAM/acceleration and hardware ownership are unknown unless
actually observed; a GPU name does not attest usable acceleration.

## Test installation and release procedure

Run unit checks with `python -m unittest discover -s infrastructure/installer-v1/tests -v`.
Run `python infrastructure/installer-v1/guided.py --probe` for read-only target
inventory. It does not install packages, touch Docker or export private logs.

For an isolated **candidate Linux host**, first provision the documented runtime
prerequisites and enough capacity, configure a resolvable local hostname and
choose its private IPv4 address. Build the matching architecture using the
existing release builder, sign the exact manifest using an offline Ed25519 key,
and deliver its public trust anchor independently. The public key next to an
untrusted download is not a trust anchor. Do not use production data or keys.

From the trusted installer directory run:

```sh
sudo python3 guided.py --bundle /path/to/signed-images --public-key /trusted/release.pem
```

Choose language, fresh mode, hostname, private bind IP and target directory.
Read the change summary and explicitly approve. Subsequent runs against the
same target offer resume; the exact release/configuration and recorded files
must match. Startup is bounded and errors retain state. After startup the installer
offers owner/HOME Space setup or login using the existing Core API. Optional web
linking requires an already configured HTTPS identity provider; use the provider
browser page then return to the installer to confirm the same local identity.
The hardware questionnaire never claims USB/audio resources. HA explicitly offers
the existing read-only import scope, probes before storing, and preserves an existing
connection. No provider token, password or session is written to installer state.
The local Kyrion UI remains available for later administration. The installer does
not infer account, recovery or backup completion from service health.

Test interruption at each stage, rerun with unchanged inputs, verify secret
hashes remain unchanged, reject a different bundle or changed managed file,
reboot and verify Docker's enabled boot service plus actual container readiness.
Verify HTTPS with the exported public leaf certificate; never disable TLS checks.
Test owner login after restart with internet disconnected. Real reboot and login
acceptance must be recorded separately from mocked orchestration tests.

Build/sign future image versions with `release/build-bundle.sh VERSION OUTPUT
linux/arm64` (or `linux/amd64`) and `release/sign-manifest.sh`. CI validates the
installer but does not establish host acceptance. Publication remains disabled;
key custody, independent trust distribution, licensing, accepted images and
clean-host evidence are prerequisites for enabling it. Installing another version
over an existing target is refused, not an update. No productive deployment,
release publication, physical action or paid call is part of this work.

Build a downloadable **unsigned Python candidate** using `python
infrastructure/installer-v1/package.py build/kyrion-installer-candidate.pyz`.
The output path must be new. Test with `python build/kyrion-installer-candidate.pyz
--probe`. It contains only allowlisted installer code/assets, requires target
Python 3.12+, stages locally in private temporary storage, and runs the same flow.
For installation, pass `--bundle`, `--public-key` and optionally `--target` as
above. It is not a native executable or a publicly authenticated release.

## Intentional remaining gaps

This implementation is **not completion of the full requested product**. The
table above is the continuing implementation backlog. In particular, native
Windows runtime/service packaging, authorized multi-device enrollment and task
transfer, existing Space selection, encrypted portable recovery/repair/uninstall,
update service/manifests/rotation, optional automatic runtime installation, signed
model recommendations/Ollama lifecycle, voice, interactive action tutorial, QR
summary and public hardware/download pages remain open. These are source work,
not merely external acceptance blockers.

External release prerequisites are protected signing-key custody and independent
trust distribution, productive identity issuer/client setup, licensing and access
to disposable supported Linux/Windows systems and physical Pi/audio/radios for
acceptance. No productive services/devices should be modified to obtain evidence.

Resume preserves tracked secrets and refuses changed files. An interruption
between an exclusive file write and its journal checkpoint requires inspection;
it is intentionally not repaired by guessing ownership. Bootstrap renewal,
certificate renewal and recovery are not silently performed. Docker's existing
restart policy is reused; bounded Compose readiness is not proof of bounded
service restart policy, standby behavior or cold-boot acceptance.

The manifest signs images, not the installer source/template distribution. The
downloaded executable/package trust chain, minimum-installer/API/schema contracts,
version selection, updates and signing-key rotation are still pending. Do not
publish these candidates as a complete signed installer.

## Operational restore continuation

See [ADR 0057](adr/0057-operational-restore-authority-transfer.md) and the
[restore evidence and boundaries](status/2026-11-13-installer-restore-updates.md).
The maintenance menu now offers restore and repair. An encrypted backup can
prepare a fresh target with `--restore BACKUP --bundle BUNDLE --public-key KEY
--target ROOT --restore-hostname HOST --restore-address ADDRESS`. The guided
review displays the authenticated runtime and backup digests before changes.
No activation occurs without the source retirement receipt.

On the source, `--retire-for-restore BACKUP --restore-target-id UUID
--transfer-receipt OUTPUT --target SOURCE` reviews the capture before explicitly
stopping and disabling owned services. Resume the target restore with
`--transfer-receipt OUTPUT`. Passwords are entered at the local protected prompt,
never supplied as command-line arguments. The receipt contains no passwords or
backup key; it authorizes only the exact backup and target UUID. Do not retire a
source before independently protecting the encrypted backup and recovery key.
These commands describe developer tooling, not a claim of complete platform
acceptance or availability of published installer artifacts.
