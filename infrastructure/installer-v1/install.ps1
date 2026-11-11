param([switch]$Probe)
$ErrorActionPreference = 'Stop'
# Windows provisioning is not available until a boot-service runtime is accepted.
# This entrypoint does not install Docker Desktop or mislabel login startup.
$entrypoint = Join-Path $PSScriptRoot 'guided.py'
if ($Probe) {
    & python $entrypoint --probe
} else {
    & python $entrypoint
}
exit $LASTEXITCODE
