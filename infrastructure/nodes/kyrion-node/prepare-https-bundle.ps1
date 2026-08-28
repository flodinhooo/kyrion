[CmdletBinding()]
param(
    [string]$DestinationRoot = "E:\Kyrion\Data\deployments"
)

$ErrorActionPreference = "Stop"
$timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$bundle = Join-Path ([System.IO.Path]::GetFullPath($DestinationRoot)) "kyrion-https-$timestamp"
$composeFile = Join-Path $PSScriptRoot "compose.platform.yml"
$caddyFile = Join-Path $PSScriptRoot "Caddyfile"

New-Item -ItemType Directory -Path $bundle | Out-Null
try {
    & docker buildx build --platform linux/arm64 --load --file (Join-Path $PSScriptRoot "Dockerfile.caddy") --tag kyrion/caddy:2.10.2 $PSScriptRoot
    if ($LASTEXITCODE -ne 0) { throw "ARM64 Caddy image build failed." }
    & docker save --output (Join-Path $bundle "caddy-arm64.tar") kyrion/caddy:2.10.2
    if ($LASTEXITCODE -ne 0) { throw "Caddy image export failed." }
    Copy-Item -LiteralPath $composeFile -Destination (Join-Path $bundle "compose.platform.yml")
    Copy-Item -LiteralPath $caddyFile -Destination (Join-Path $bundle "Caddyfile")

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
    Write-Warning "The incomplete HTTPS bundle was removed: $bundle"
    throw
}
