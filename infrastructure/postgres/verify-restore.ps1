[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Backup,
    [Parameter(Mandatory = $true)]
    [string]$Container,
    [string]$DatabaseUser = "kyrion",
    [switch]$ReadOnlyManifest
)

$ErrorActionPreference = "Stop"
$backupPath = (Resolve-Path -LiteralPath $Backup).Path
$manifestPath = "$backupPath.json"
$verificationId = [Guid]::NewGuid().ToString("N")
$verificationDatabase = "kyrion_restore_verify_$verificationId"
$containerBackup = "/tmp/$verificationDatabase.dump"

if (!(Test-Path -LiteralPath $manifestPath)) {
    throw 'BACKUP_MANIFEST_REQUIRED: checksum verification is mandatory before restore.'
}
if (Test-Path -LiteralPath $manifestPath) {
    $manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
    $actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $backupPath).Hash.ToLowerInvariant()
    if ($manifest.format -ne "kyrion-postgresql-backup" -or $manifest.formatVersion -ne 1 -or $manifest.sha256 -ne $actualHash) {
        throw "Backup manifest or SHA-256 checksum is invalid."
    }
}

# Never create scratch databases inside an installed/personal cluster. A label
# alone is insufficient: require no network, published ports or persistent data.
$targetJson = & docker inspect $Container
if ($LASTEXITCODE -ne 0) { throw 'ISOLATED_RESTORE_TARGET_REQUIRED: container inspection failed.' }
$target = @($targetJson | ConvertFrom-Json)[0]
if ($target.Id -notmatch '^[a-f0-9]{64}$' -or
    $target.Config.Labels.'io.kyrion.restore-target' -ne 'true' -or
    $target.HostConfig.NetworkMode -ne 'none' -or
    @($target.HostConfig.PortBindings.PSObject.Properties | Where-Object { $_.Value }).Count -ne 0 -or
    !(@($target.HostConfig.Tmpfs.PSObject.Properties.Name) -contains '/var/lib/postgresql/data') -or
    @($target.Mounts | Where-Object { $_ -and $_.Type -ne 'tmpfs' }).Count -ne 0 -or
    !$target.State.Running) {
    throw 'ISOLATED_RESTORE_TARGET_REQUIRED: use a marked network-none, unpublished, tmpfs-only PostgreSQL fixture.'
}
# Pin the inspected identity rather than following a concurrently reused name.
$Container = $target.Id
$databaseCreated = $false
try {
    & docker cp $backupPath "${Container}:${containerBackup}"
    if ($LASTEXITCODE -ne 0) { throw "docker cp failed with exit code $LASTEXITCODE" }

    & docker exec $Container createdb --username=$DatabaseUser --template=template0 $verificationDatabase
    if ($LASTEXITCODE -ne 0) { throw "Temporary verification database creation failed with exit code $LASTEXITCODE" }
    $databaseCreated = $true

    & docker exec $Container pg_restore --exit-on-error --no-owner --no-acl --username=$DatabaseUser --dbname=$verificationDatabase $containerBackup
    if ($LASTEXITCODE -ne 0) { throw "pg_restore failed with exit code $LASTEXITCODE" }

    $migrationResult = (& docker exec $Container psql --username=$DatabaseUser --dbname=$verificationDatabase --tuples-only --no-align --command "SELECT COALESCE(MAX(version::integer)::text, 'none') || ':' || bool_and(success) FROM flyway_schema_history;").Trim()
    if ($LASTEXITCODE -ne 0 -or $migrationResult -notmatch "^[0-9]+:t(rue)?$") {
        throw "Restored Flyway history is incomplete: $migrationResult"
    }

    $tableCount = [int](& docker exec $Container psql --username=$DatabaseUser --dbname=$verificationDatabase --tuples-only --no-align --command "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';")
    if ($LASTEXITCODE -ne 0 -or $tableCount -lt 1) { throw "Restored database contains no public tables." }

    if (!$ReadOnlyManifest) {
        $manifest.restoreVerified = $true
        $manifest | Add-Member -NotePropertyName restoreVerifiedAt -NotePropertyValue ((Get-Date).ToUniversalTime().ToString("o")) -Force
        $manifest | Add-Member -NotePropertyName restoreVerification -NotePropertyValue ([ordered]@{ flyway = $migrationResult; publicTables = $tableCount }) -Force
        $manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $manifestPath -Encoding utf8
    }

    [ordered]@{ verified = $true; flyway = $migrationResult; publicTables = $tableCount; productionDatabaseChanged = $false } | ConvertTo-Json
}
finally {
    if ($databaseCreated) { & docker exec $Container dropdb --if-exists --force --username=$DatabaseUser $verificationDatabase 2>$null }
    & docker exec $Container rm -f $containerBackup 2>$null
}
