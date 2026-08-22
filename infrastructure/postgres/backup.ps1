[CmdletBinding()]
param(
    [string]$Container = "kyrion-postgres",
    [string]$Database = "kyrion",
    [string]$DatabaseUser = "kyrion",
    [string]$Destination = "E:\Kyrion\Data\backups\postgres"
)

$ErrorActionPreference = "Stop"
$timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$backupName = "kyrion-postgres-$timestamp.dump"
$containerBackup = "/tmp/$backupName"
$destinationPath = [System.IO.Path]::GetFullPath($Destination)
$backupPath = Join-Path $destinationPath $backupName

New-Item -ItemType Directory -Force -Path $destinationPath | Out-Null

try {
    & docker exec $Container pg_dump --format=custom --compress=9 --no-owner --no-acl --username=$DatabaseUser --file=$containerBackup $Database
    if ($LASTEXITCODE -ne 0) { throw "pg_dump failed with exit code $LASTEXITCODE" }

    & docker cp "${Container}:${containerBackup}" $backupPath
    if ($LASTEXITCODE -ne 0) { throw "docker cp failed with exit code $LASTEXITCODE" }

    $file = Get-Item -LiteralPath $backupPath
    $hash = Get-FileHash -Algorithm SHA256 -LiteralPath $backupPath
    $postgresVersion = (& docker exec $Container psql --username=$DatabaseUser --dbname=$Database --tuples-only --no-align --command "SHOW server_version;").Trim()
    if ($LASTEXITCODE -ne 0) { throw "PostgreSQL version lookup failed with exit code $LASTEXITCODE" }

    [ordered]@{
        format = "kyrion-postgresql-backup"
        formatVersion = 1
        createdAt = (Get-Date).ToUniversalTime().ToString("o")
        database = $Database
        postgresVersion = $postgresVersion
        file = $file.Name
        bytes = $file.Length
        sha256 = $hash.Hash.ToLowerInvariant()
        restoreVerified = $false
    } | ConvertTo-Json | Set-Content -LiteralPath "$backupPath.json" -Encoding utf8

    Write-Output $backupPath
}
finally {
    & docker exec $Container rm -f $containerBackup 2>$null
}
