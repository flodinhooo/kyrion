param(
    [Parameter(Mandatory=$true)][string]$Version,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [string]$Platform = "linux/arm64",
    [string]$CoreContext = "services/core",
    [string]$WebContext = "apps/web"
)
$ErrorActionPreference = "Stop"
if ($Version -match "latest|[^A-Za-z0-9._-]") { throw "Version must be immutable and must not contain latest" }
if ($Platform -notin @("linux/arm64", "linux/amd64")) { throw "Unsupported image architecture" }
$imageArch = $Platform.Split('/')[1]
$out = [IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Force -Path $out | Out-Null
$coreTag = "kyrion/core:$Version"
$webTag = "kyrion/web:$Version"
$postgresTag = "postgres:17.6-alpine"
$caddyTag = "caddy:2.10.2-alpine"
docker buildx build --platform $Platform --load --tag $coreTag $CoreContext
if ($LASTEXITCODE) { throw 'Core image build failed' }
docker buildx build --platform $Platform --load --tag $webTag $WebContext
if ($LASTEXITCODE) { throw 'Web image build failed' }
docker pull --platform $Platform $postgresTag
if ($LASTEXITCODE) { throw 'PostgreSQL image pull failed' }
docker pull --platform $Platform $caddyTag
if ($LASTEXITCODE) { throw 'Caddy image pull failed' }
docker image save --output (Join-Path $out "kyrion-core-$imageArch.tar") $coreTag
if ($LASTEXITCODE) { throw 'Core image save failed' }
docker image save --output (Join-Path $out "kyrion-web-$imageArch.tar") $webTag
if ($LASTEXITCODE) { throw 'Web image save failed' }
docker image save --output (Join-Path $out "postgres-$imageArch.tar") $postgresTag
if ($LASTEXITCODE) { throw 'PostgreSQL image save failed' }
docker image save --output (Join-Path $out "caddy-$imageArch.tar") $caddyTag
if ($LASTEXITCODE) { throw 'Caddy image save failed' }
$artifacts = Get-ChildItem -LiteralPath $out -File | Where-Object { $_.Name -like "*.tar" } | ForEach-Object {
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant()
    [ordered]@{ name=$_.Name; sha256=$hash; bytes=$_.Length }
}
$manifest = [ordered]@{ schemaVersion=1; release=$Version; architecture=$Platform; artifacts=@($artifacts) }
if ($artifacts.Count -ne 4) { throw 'Expected exactly four image archives in output directory' }
$manifestPath = Join-Path $out "manifest.json"
($manifest | ConvertTo-Json -Depth 5 -Compress) + "`n" | Set-Content -LiteralPath $manifestPath -Encoding utf8NoBOM
Write-Output "Created unsigned bundle manifest: $manifestPath"
Write-Output "Sign the exact manifest bytes with sign-manifest.sh using an offline Ed25519 key."
