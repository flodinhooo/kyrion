# Narrow UAC entry point: installs/verifies only the two approved firewall guards.
# No Core restart, configuration update, DNS operation or Pi connection here.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$directory = Join-Path $root '.run/dev-recovery/sprint04'
New-Item -ItemType Directory -Path $directory -Force | Out-Null
try {
    & (Join-Path $PSScriptRoot 'Install-CoreLanGuards.ps1') -Apply |
        Set-Content -LiteralPath (Join-Path $directory 'guard-install-result.json') -Encoding UTF8
} catch {
    @{applied=$false; errorType=$_.Exception.GetType().Name; message=$_.Exception.Message} |
        ConvertTo-Json | Set-Content -LiteralPath (Join-Path $directory 'guard-install-result.json') -Encoding UTF8
    exit 1
}
