# PostgreSQL Backup and Restore Verification

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
.\infrastructure\postgres\verify-restore.ps1 -Backup "E:\Kyrion\Data\backups\postgres\kyrion-postgres-YYYYMMDDTHHMMSSZ.dump"
```

The verifier checks the manifest checksum, restores into a randomly named
temporary database, validates successful Flyway history and public tables, then
removes the temporary database. On success it updates the manifest with the
verification time and observed schema facts. Restore verification does not test
application behaviour, credentials outside PostgreSQL, provider state or
gateway/coordinator backups.

For an actual disaster recovery, stop Core, restore into a separately prepared
database first, validate it, and only then change Core's database target. Do not
restore over the active production database.
