[CmdletBinding()]
param()

# Read-only preflight. Does not build, export, restart or replace anything.
$ErrorActionPreference = "Stop"
$repository = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$compose = Join-Path $PSScriptRoot "compose.platform.yml"
$example = Join-Path $PSScriptRoot ".env.platform.example"
foreach ($relative in @("apps/web/Dockerfile", "apps/web/pnpm-lock.yaml", "services/core/Dockerfile", "services/core/gradlew")) {
    if (-not (Test-Path -LiteralPath (Join-Path $repository $relative) -PathType Leaf)) {
        throw "Missing build input: $relative"
    }
}
$webIgnore = Get-Content -LiteralPath (Join-Path $repository "apps/web/.dockerignore")
foreach ($pattern in @(".env", ".env.*", ".next", ".next-review", "node_modules")) {
    if ($webIgnore -notcontains $pattern) { throw "Web Docker context does not exclude $pattern" }
}
& docker version --format '{{.Server.Version}}'
if ($LASTEXITCODE -ne 0) { throw "Docker Engine is unavailable." }
& docker buildx version
if ($LASTEXITCODE -ne 0) { throw "Docker Buildx is unavailable." }
& docker compose --env-file $example -f $compose config --quiet
if ($LASTEXITCODE -ne 0) { throw "Platform Compose validation failed." }
Write-Output "PASS: Docker, Buildx, Compose and source inputs are ready for the later ARM64 image build."
Write-Output "Existing installation: preserve the Pi environment, database and keys; do not rerun install-platform.sh."
