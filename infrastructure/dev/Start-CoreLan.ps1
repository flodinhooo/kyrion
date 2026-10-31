[CmdletBinding()]
param([string]$Manifest, [switch]$ValidateOnly, [switch]$Wait)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
if (!$Manifest) { $Manifest = Join-Path $root '.run/dev-recovery/core-lan.json' }
. (Join-Path $PSScriptRoot 'Test-CoreLanGuards.ps1')
$pin = Read-CoreLanManifest -Root $root -Manifest $Manifest
$java = Assert-CoreLanGuards -Root $root
& (Join-Path $root 'services/ai/.venv/Scripts/python.exe') (Join-Path $PSScriptRoot 'Verify-CoreRuntime.py') $pin.artifact
if ($LASTEXITCODE -ne 0) { throw 'RUNTIME_MIGRATION_OR_LEASE_CHECK_FAILED' }
if ($ValidateOnly) {
    @{validated=$true; artifactSha256=$pin.artifactSha256; bind='0.0.0.0'; guardsVerified=$true} | ConvertTo-Json
    return
}
$socket = New-Object Net.Sockets.TcpClient
try {
    $connect = $socket.ConnectAsync('127.0.0.1',8080)
    try { if ($connect.Wait(500) -and $socket.Connected) { throw 'CORE_PORT_OCCUPIED' } }
    catch { if ($_.Exception.Message -eq 'CORE_PORT_OCCUPIED') { throw } }
} finally { $socket.Dispose() }
$directory = Join-Path $root ('.run/dev-recovery/guarded-start-' + [guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $directory | Out-Null
$copy = Join-Path $directory 'core-runtime.jar'
Copy-Item -LiteralPath $pin.artifact -Destination $copy
if ((Get-FileHash -LiteralPath $copy -Algorithm SHA256).Hash -ine $pin.artifactSha256) { throw 'PINNED_CORE_ARTIFACT_MISMATCH' }
$saved = $env:KYRION_CORE_ADDRESS
$launched = $null
try {
    $env:KYRION_CORE_ADDRESS = '0.0.0.0'
    $launched = Start-Process -FilePath $java -ArgumentList @('-jar', ('"' + $copy + '"')) -WorkingDirectory (Join-Path $root 'services/core') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $directory 'core.out.log') -RedirectStandardError (Join-Path $directory 'core.err.log') -PassThru
    $deadline = (Get-Date).AddSeconds(90)
    $ready = $false
    while ((Get-Date) -lt $deadline -and !$launched.HasExited) {
        try { if ((Invoke-RestMethod 'http://127.0.0.1:8080/actuator/health' -TimeoutSec 2).status -eq 'UP') { $ready=$true; break } } catch { }
        Start-Sleep -Seconds 1
    }
    if (!$ready) { throw 'CORE_HEALTH_DEADLINE' }
    & (Join-Path $PSScriptRoot 'Probe-PiCore.ps1')
    if ($LASTEXITCODE -ne 0) { throw 'PI_CORE_ACCEPTANCE_FAILED' }
    @{started=$true; coreProcessId=$launched.Id; artifact=$copy; artifactSha256=$pin.artifactSha256; bind='0.0.0.0'; guardsVerified=$true} |
        ConvertTo-Json | Tee-Object -FilePath (Join-Path $directory 'result.json')
    if ($Wait) { $launched.WaitForExit(); exit $launched.ExitCode }
} catch {
    if ($launched -and !$launched.HasExited) { Stop-Process -Id $launched.Id }
    throw
} finally { $env:KYRION_CORE_ADDRESS = $saved }
