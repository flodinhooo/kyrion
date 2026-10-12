param(
    [Parameter(Mandatory=$true)][string]$Version,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [string]$Platform = "linux/arm64",
    [string]$CoreContext = "services/core",
    [string]$WebContext = "apps/web"
)
$ErrorActionPreference = "Stop"
if ($Version -match "latest|[^A-Za-z0-9._-]") { throw "Version must be immutable and must not contain latest" }
if ($Platform -ne "linux/arm64") { throw "Installer v1 only supports linux/arm64" }
$out = [IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Force -Path $out | Out-Null
$coreTag = "kyrion/core:$Version"
$webTag = "kyrion/web:$Version"
$postgresTag = "postgres:17.6-alpine"
$caddyTag = "caddy:2.10.2-alpine"
docker buildx build --platform $Platform --load --tag $coreTag $CoreContext
docker buildx build --platform $Platform --load --tag $webTag $WebContext
docker pull --platform $Platform $postgresTag
docker pull --platform $Platform $caddyTag
docker image save --output (Join-Path $out "kyrion-core-arm64.tar") $coreTag
docker image save --output (Join-Path $out "kyrion-web-arm64.tar") $webTag
docker image save --output (Join-Path $out "postgres-arm64.tar") $postgresTag
docker image save --output (Join-Path $out "caddy-arm64.tar") $caddyTag
$artifacts = Get-ChildItem -LiteralPath $out -File | Where-Object { $_.Name -like "*.tar" } | ForEach-Object {
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant()
    [ordered]@{ name=$_.Name; sha256=$hash; bytes=$_.Length }
}
$manifest = [ordered]@{ schemaVersion=1; release=$Version; architecture=$Platform; artifacts=@($artifacts) }
$manifestPath = Join-Path $out "manifest.json"
($manifest | ConvertTo-Json -Depth 5 -Compress) + "`n" | Set-Content -LiteralPath $manifestPath -Encoding utf8NoBOM
Write-Output "Created unsigned bundle manifest: $manifestPath"
Write-Output "Sign the exact manifest bytes with sign-manifest.sh using an offline Ed25519 key."
