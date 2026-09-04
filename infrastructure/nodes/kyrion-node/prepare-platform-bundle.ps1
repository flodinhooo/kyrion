[CmdletBinding()]
param(
    [string]$DestinationRoot = "E:\Kyrion\Data\deployments",
    [string]$CredentialKey = "E:\Kyrion\Data\secrets\credential.key",
    [string]$AuditIntegrityKey = "E:\Kyrion\Data\secrets\audit-integrity.key",
    [string]$AiBaseUrl = "http://192.168.1.107:8000"
)

$ErrorActionPreference = "Stop"
$repository = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$environmentFile = Join-Path $repository "infrastructure\.env"
$composeFile = Join-Path $PSScriptRoot "compose.platform.yml"
$timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$bundle = Join-Path ([System.IO.Path]::GetFullPath($DestinationRoot)) "kyrion-platform-$timestamp"

foreach ($required in @($environmentFile, $composeFile, $CredentialKey, $AuditIntegrityKey)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Required file is missing: $required"
    }
}

$settings = @{}
Get-Content -LiteralPath $environmentFile | ForEach-Object {
    if ($_ -match '^([^#=]+)=(.*)$') {
        $settings[$matches[1]] = $matches[2]
    }
}
foreach ($requiredSetting in @("KYRION_POSTGRES_DB", "KYRION_POSTGRES_USER")) {
    if ([string]::IsNullOrWhiteSpace($settings[$requiredSetting])) {
        throw "Missing required setting in infrastructure/.env: $requiredSetting"
    }
}
if ($settings["KYRION_POSTGRES_USER"] -ne "kyrion" -or $settings["KYRION_POSTGRES_DB"] -ne "kyrion") {
    throw "The first Pi migration requires database and user name 'kyrion'."
}
foreach ($keyPath in @($CredentialKey, $AuditIntegrityKey)) {
    if ((Get-Item -LiteralPath $keyPath).Length -ne 32) {
        throw "Key must contain exactly 32 bytes: $keyPath"
    }
}

New-Item -ItemType Directory -Path $bundle | Out-Null
try {
    $targetPasswordBytes = New-Object byte[] 32
    $random = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $random.GetBytes($targetPasswordBytes)
    }
    finally {
        $random.Dispose()
    }
    $targetPassword = -join ($targetPasswordBytes | ForEach-Object { $_.ToString("x2") })
    Push-Location $repository
    try {
        & docker buildx build --platform linux/arm64 --load --tag kyrion/core:pi-local services/core
        if ($LASTEXITCODE -ne 0) { throw "ARM64 Core image build failed." }
        & docker buildx build --platform linux/arm64 --load --tag kyrion/web:pi-local apps/web
        if ($LASTEXITCODE -ne 0) { throw "ARM64 Web image build failed." }
    }
    finally {
        Pop-Location
    }

    & docker save --output (Join-Path $bundle "kyrion-core-arm64.tar") kyrion/core:pi-local
    if ($LASTEXITCODE -ne 0) { throw "Core image export failed." }
    & docker save --output (Join-Path $bundle "kyrion-web-arm64.tar") kyrion/web:pi-local
    if ($LASTEXITCODE -ne 0) { throw "Web image export failed." }

    $containerDump = "/tmp/kyrion-platform-$timestamp.dump"
    try {
        & docker exec kyrion-postgres pg_dump --format=custom --compress=9 --no-owner --no-acl --username=kyrion --file=$containerDump kyrion
        if ($LASTEXITCODE -ne 0) { throw "PostgreSQL backup failed." }
        & docker cp "kyrion-postgres:${containerDump}" (Join-Path $bundle "database.dump")
        if ($LASTEXITCODE -ne 0) { throw "PostgreSQL backup export failed." }
    }
    finally {
        & docker exec kyrion-postgres rm -f $containerDump 2>$null
    }

    Copy-Item -LiteralPath $composeFile -Destination (Join-Path $bundle "compose.platform.yml")
    Copy-Item -LiteralPath $CredentialKey -Destination (Join-Path $bundle "credential.key")
    Copy-Item -LiteralPath $AuditIntegrityKey -Destination (Join-Path $bundle "audit-integrity.key")
    @(
        "KYRION_VERSION=pi-local"
        "KYRION_POSTGRES_DB=kyrion"
        "KYRION_POSTGRES_USER=kyrion"
        "KYRION_POSTGRES_PASSWORD=$targetPassword"
        "KYRION_AI_BASE_URL=$AiBaseUrl"
        "KYRION_SPOTIFY_CLIENT_ID=$($settings['KYRION_SPOTIFY_CLIENT_ID'])"
        "KYRION_SPOTIFY_CLIENT_SECRET=$($settings['KYRION_SPOTIFY_CLIENT_SECRET'])"
        "KYRION_SPOTIFY_REDIRECT_URI=$($settings['KYRION_SPOTIFY_REDIRECT_URI'])"
    ) | Set-Content -LiteralPath (Join-Path $bundle "platform.env") -Encoding utf8

    $hashes = Get-ChildItem -LiteralPath $bundle -File | Sort-Object Name | ForEach-Object {
        $hash = Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName
        "{0}  {1}" -f $hash.Hash.ToLowerInvariant(), $_.Name
    }
    $hashes | Set-Content -LiteralPath (Join-Path $bundle "SHA256SUMS") -Encoding ascii
    Write-Output $bundle
}
catch {
    if (Test-Path -LiteralPath $bundle) {
        Remove-Item -LiteralPath $bundle -Recurse -Force
    }
    Write-Warning "The incomplete deployment bundle was removed: $bundle"
    throw
}
