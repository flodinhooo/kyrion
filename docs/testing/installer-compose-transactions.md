# Isolated Compose transaction developer test

This fixture builds actual Core and Web images, prepares signed test bundles,
installs them in a new daemon-host directory, and exercises the existing installer
transaction. It does not publish a release, install host services or perform
device commands. Run only on a development machine with enough disk and RAM.

Requirements: local rootful Linux Docker daemon, local `default` builder using
the `docker` driver, Linux amd64 execution, Python 3.12+ with installer crypto
dependencies, Git, built current Core and knowledge-parser JARs. Only a Unix or
local Windows named-pipe endpoint is accepted. Public base images and package
dependencies are downloaded. Remote/cloud builders are refused.

From the repository root, using the developer Python environment:

```powershell
python infrastructure/installer-v1/tests/integration/prepare-compose-fixture.py `
  --docker 'C:/Program Files/Docker/Docker/resources/bin/docker.exe' `
  --repository . --work build `
  --core-jar build/core-linked-output/libs/kyrion-core-0.1.0-SNAPSHOT.jar `
  --parser-jar build/core-linked-output/libs/knowledge-parser.jar
```

The command prints the newly generated fixture manifest path. Pass its containing
directory to the launcher; no fixture ID or existing installation is guessed:

```powershell
python infrastructure/installer-v1/tests/integration/run-compose-fixture.py `
  --docker 'C:/Program Files/Docker/Docker/resources/bin/docker.exe' `
  --fixture <generated-fixture-directory>
```

Each launcher invocation creates a new `runs/<random-id>` below that directory
and a matching private `/var/lib/installer-fixtures/<random-id>` on the Docker
VM. The Debian 13 worker binds that directory at the identical absolute path so
Compose child bind mounts refer to real daemon-host files. Only the loopback HTTPS
port 443 is published. A port conflict is a refusal, not permission to stop
another service. The worker uses the daemon socket to manage only its own
installation project and labeled retention containers.

The target Core JAR adds a synthetic V50 migration to the actual source schema
49. Test signing keys are ephemeral; public test trust and signatures may be
retained, private signing keys are never written. Local owner credentials and
backup passwords stay in memory. Core/PG configuration and encrypted backups are
private fixture data. Nothing is uploaded.

The driver checks real authenticated bundle loading, fresh/repeated setup, Core
and Web TLS readiness, GPG-encrypted backups, a PG template snapshot, Flyway
migration, interrupted activation, continuation and explicit post-activation
recovery. It also checks that recovery restores the original schema, knowledge
and local owner identity. No household integration is configured.

Three prerequisite observations are explicitly injected: loopback eligibility,
systemd Docker active/enabled probes, and global discovery of unrelated Kyrion
installations already present on a shared developer daemon. Production checks
are unchanged. All project operations and health results are real. This is
container integration evidence, **not** systemd installation, whole-host reboot,
Windows, browser SSO, physical hardware or distributed-installation acceptance.
The report must retain these boundaries.

Inspect `runs/<id>/transaction-run.log` on failure. A report appears only when all
assertions pass; a build or downloaded archive alone is not success. Cleanup
verifies the private marker and project/transaction labels, gracefully stops and
removes only owned containers. Private VM fixture data and owned image caches
remain for explicit forensic inspection; no shared volumes/images are pruned.
The full installer requirements ledger remains open regardless of this fixture.
