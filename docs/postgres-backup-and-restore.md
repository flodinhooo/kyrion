# PostgreSQL Backup and Restore Verification

K-Data originals live outside PostgreSQL. For knowledge backup/restore, stop Core
and back up the configured document root together with the matching database.
See [K-Data operations](k-data.md#backup-restore-and-upgrades); database-only
backups and personal JSON exports do not include original document files.

Kyrion keeps operational PostgreSQL backups outside the repository. A backup is
not considered recoverable merely because `pg_dump` completed: the companion
manifest records its SHA-256 checksum and remains `restoreVerified: false` until
an isolated restore drill succeeds.

Create a backup from the running local container:

```powershell
.\infrastructure\postgres\backup.ps1
```

The default destination is `E:\Kyrion\Data\backups\postgres`. Override it with
`-Destination` when the protected backup volume lives elsewhere. Protect that
directory with operating-system access controls and volume encryption because a
database dump contains account hashes and private application data.

Verify a specific backup without modifying the production database:

```powershell
# Prepare a disposable fixture using an already reviewed local PostgreSQL17
# image ID. No pull/update, published port, persistent volume or socket mount.
docker run -d --name kyrion-restore-owner-check --network none --label io.kyrion.restore-target=true --tmpfs /var/lib/postgresql/data -e POSTGRES_HOST_AUTH_METHOD=trust -e POSTGRES_USER=kyrion '<reviewed-local-image-id>'
# Wait for pg_isready -U kyrion inside this fixture before verification.
.\infrastructure\postgres\verify-restore.ps1 -Backup "E:\Kyrion\Data\backups\postgres\kyrion-postgres-YYYYMMDDTHHMMSSZ.dump" -Container kyrion-restore-owner-check -ReadOnlyManifest
# Remove only this positively identified owner-created fixture after the check.
docker rm -f kyrion-restore-owner-check
```

The verifier refuses missing manifests before contacting Docker, checks the
manifest checksum and requires an explicitly supplied isolated container.
It rejects unmarked, networked, published, stopped or persistent targets before
copying a dump or creating any database. It pins the inspected container ID,
restores into a randomly named temporary database, validates
successful Flyway history/public tables and removes the temporary database.
The trust setting above is only for an unpublished, network-none disposable
fixture; it is not an installation authentication setting. Never pass the
personal `kyrion-postgres` container. Keep the fixture stopped/removed when done.
See [V40 rollout and old-binary rollback boundaries](v40-rollout.md).
Without `-ReadOnlyManifest`, success updates the manifest with the
verification time and observed schema facts. Restore verification does not test
application behaviour, credentials outside PostgreSQL, provider state or
gateway/coordinator backups.

Guard regressions use a fake Docker command and synthetic files:
`python -m unittest discover -s infrastructure/postgres -p test_verify_restore.py -v`.
Current original-key and nonempty-file evidence plus the planned host/off-host
procedure are in [the acceptance gates](status/2026-11-07-acceptance-gates.md) and
[host recovery plan](host-recovery-acceptance.md). A successful same-host drill
does not establish off-host recovery or freshness of all post-backup writes.

The PostgreSQL dump does not contain `audit-integrity.key`. Back up that file
separately using protected secret storage; never place it beside an unencrypted
dump or commit it to the repository. Without the original key, restored audit
events cannot be cryptographically verified.

For an actual disaster recovery, stop Core, restore into a separately prepared
database first, validate it, and only then change Core's database target. Do not
restore over the active production database.
