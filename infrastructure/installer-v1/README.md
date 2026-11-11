# Kyrion local guided installer

This directory extends the existing fresh installer; it is **not a publicly
released, fully accepted consumer installer**. All setup state lives locally in
the downloaded installer and existing Core. kyrion.ch remains a download/help
surface. No website-hosted installation wizard is used.

Read [inventory, stages, support matrix and acceptance](../../docs/guided-installer.md)
and [ADR 0045](../../docs/adr/0045-guided-local-installer.md).

## Run

Python 3.12+ is required. Inspect the actual target without modifying it:

```sh
python guided.py --probe
```

Windows also has `install.ps1 -Probe`. Windows provisioning is unavailable;
Docker Desktop startup after sign-in is not system boot support.

On an isolated candidate Debian 13 x64/ARM64 or 64-bit Raspberry Pi OS 13 host
with Docker Engine, Compose v2, OpenSSL and an enabled Docker system service:

```sh
sudo python3 guided.py --bundle /path/to/signed-images --public-key /trusted/release.pem
# Or: ./install.sh --bundle /path/to/signed-images --public-key /trusted/release.pem
```

The guided terminal flow supports German and English, fresh installation and
same-release resume. It reviews the exact release, image sizes, dedicated target,
private LAN binding and system changes before asking for explicit approval.
No additional package/runtime/model is installed implicitly.

The four signed images are authenticated, hashed and checked against their loaded
IDs/platforms. The installer creates private raw 32-byte Core keys, random database
and bootstrap credentials, a local leaf certificate and runtime-only Compose.
Only HTTPS on the explicitly chosen private LAN IPv4 address is published.
Core and local HTTPS readiness are checked separately with TLS verification enabled.

You may continue owner/HOME Space setup directly in the installer through the
existing Core API, or sign into the same account on resume. Passwords and bearer
tokens travel through child-process stdin, never command arguments or journals.
Optional central linking uses Core's existing RFC8628 browser authorization and
requires an already configured HTTPS provider. Its public productive availability
is not established by this source change. No website password is collected.

Hardware choices are recorded without claiming a controller or microphone.
Optional Home Assistant connection performs a real Core probe before Core stores
encrypted credentials and imports devices. Current scope is explicitly **all
supported registry-backed devices, read-only**, with existing room-name mapping.
Selection of individual HA devices and HA control remain unavailable. An existing
connection is preserved. No physical action is executed.

## Resume and maintenance

Rerun with identical target/hostname/IP/release and choose `resume`. A private,
atomic journal and exclusive process lock prevent parallel writes; recorded files
must match. Existing installations without this journal are refused. No database,
foreign Ollama installation or unrelated file is deleted. Ambiguous files created
just before a checkpoint are preserved and require inspection, rather than silently
replacing a key. Resume from every possible instruction boundary is not yet proven.

Use `./verify.sh /var/lib/kyrion-install` to recheck files and live health.
The public certificate is `TARGET/data/tls/cert.pem`; verify origin and establish
client trust through normal OS mechanisms. Never copy the private key or disable
TLS verification. Certificate renewal is not automated yet (365-day expiry).
Core expires the protected bootstrap secret after 30 minutes. Automatic renewal
of an expired unclaimed bootstrap is not implemented; do not change its timestamp
or recreate it on an initialized installation.

The existing local Kyrion UI retains profile, Space, integrations and diagnostics.
Installer completion means service readiness plus separately reported setup facts;
it does not attest offline reboot login, recovery, backup or updates.

Extend, repair, restore, uninstall, distributed task transfer, native Windows
installation, model/voice installation, backup scheduling and updating remain
explicit pending stages. Do not use the old migration scripts as a general updater.

## Verification and releases

```sh
python -m unittest discover -s tests -v
python -m compileall -q .
```

CI runs tests on Linux and Windows; shell/signature/Compose checks run on Linux.
These are source checks, not host acceptance. Build and sign matching image bundles:

```sh
sh release/build-bundle.sh 1.0.0 /new/empty/output linux/arm64
sh release/sign-manifest.sh /new/empty/output/manifest.json /offline/private.pem /new/empty/output/manifest.sig
sh release/verify-manifest.sh /new/empty/output/manifest.json /new/empty/output/manifest.sig /trusted/public.pem
```

The PowerShell builder also accepts `-Platform linux/amd64`. Package the existing
installer code and assets into a downloadable Python archive with:

```sh
python package.py /existing/output/kyrion-installer.pyz
python /existing/output/kyrion-installer.pyz --probe
sudo python3 /existing/output/kyrion-installer.pyz --bundle /path/to/signed-images --public-key /trusted/release.pem
```

The packager includes only allowlisted source/templates/locales and refuses to
overwrite an artifact. It excludes host data, release keys, .env, tests and caches.
The archive requires Python 3.12+ on the target; it is not a native Windows
executable or a bundled Python runtime. It is an **unsigned candidate** and its
SHA-256 is not proof of authenticity. Distribute trusted installer code/templates
separately from signed image artifacts; the current manifest authenticates images
only. No public download link is generated. The placeholder cannot install.

The protected release-signing environment and disabled publication gate remain
unchanged. Release key custody/rotation, independently delivered trust anchors,
licensing, accepted platform images, full recovery and clean-host/reboot evidence
must be resolved before publication. Nothing was deployed or published by this work.
