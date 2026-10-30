[CmdletBinding()]
param([Parameter(Mandatory=$true)][int]$CoreProcessId, [switch]$Apply)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$review = & (Join-Path $PSScriptRoot 'Set-CoreLan.ps1') -CoreProcessId $CoreProcessId | ConvertFrom-Json
$java = (Resolve-Path (Join-Path $root '.run/dev-recovery/toolchain/jdk-21.0.13.0.2+1/bin/java.exe')).Path
$directory = Join-Path $root ('.run/dev-recovery/sprint04/activation-' + [guid]::NewGuid().ToString())
if (!$Apply) {
    @{apply=$false; originalProcess=$CoreProcessId; originalArtifactSha256=$review.artifactSha256; program=$java; bind='0.0.0.0'; requiresVerifiedGuards=$true} | ConvertTo-Json
    return
}
# Only the explicitly approved listener, same JAR and verified Core process.
$names = @('Kyrion-CoreLan-Guard-NonPi-v1','Kyrion-CoreLan-Guard-NonPrivate-v1')
$expectedRanges = Get-Content (Join-Path $PSScriptRoot 'core-lan-guard-addresses.json') -Raw | ConvertFrom-Json
# Load the same normalization helper without installing or modifying any rule.
. (Join-Path $PSScriptRoot 'Install-CoreLanGuards.ps1') | Out-Null
foreach ($name in $names) {
    $rule = Get-NetFirewallRule -PolicyStore ActiveStore -Name $name -ErrorAction Stop
    $application = $rule | Get-NetFirewallApplicationFilter
    $port = $rule | Get-NetFirewallPortFilter
    $address = $rule | Get-NetFirewallAddressFilter
    $expectedProfile = if ($name -eq $names[0]) { 'Any' } else { 'Domain, Public' }
    $expectedRemote = if ($name -eq $names[0]) { $expectedRanges } else { @('Any') }
    if ($rule.Enabled.ToString() -ne 'True' -or $rule.Action.ToString() -ne 'Block' -or $rule.Direction.ToString() -ne 'Inbound' -or
        $rule.PrimaryStatus.ToString() -ne 'OK' -or $rule.Profile.ToString() -ne $expectedProfile -or
        $application.Program -ine $java -or $port.Protocol -ne 'TCP' -or $port.LocalPort -ne '8080' -or
        (Compare-Object @($address.RemoteAddress | ForEach-Object { ConvertTo-CoreFirewallAddress $_ } | Sort-Object) @($expectedRemote | ForEach-Object { ConvertTo-CoreFirewallAddress $_ } | Sort-Object))) {
        throw 'EFFECTIVE_FIREWALL_GUARD_MISMATCH'
    }
}
$profiles = Get-NetFirewallProfile -PolicyStore ActiveStore
if ($profiles | Where-Object { $_.Enabled.ToString() -ne 'True' -or $_.DefaultInboundAction.ToString() -ne 'Block' }) { throw 'FIREWALL_DISABLED_OR_UNSAFE' }
& python.exe (Join-Path $PSScriptRoot 'Verify-CoreRuntime.py') $review.artifact
if ($LASTEXITCODE -ne 0) { throw 'RUNTIME_MIGRATION_OR_LEASE_CHECK_FAILED' }
$current = Get-CimInstance Win32_Process -Filter "ProcessId=$CoreProcessId"
if (!$current -or $current.CreationDate.ToString('o') -ne $review.processCreated) { throw 'CORE_PROCESS_CHANGED' }
$children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$CoreProcessId")
$originalJava = ($children | Where-Object Name -eq 'java.exe' | Select-Object -First 1).ExecutablePath
if (!$originalJava -or !(Test-Path -LiteralPath $originalJava)) { throw 'ROLLBACK_JAVA_UNAVAILABLE' }
New-Item -ItemType Directory -Path $directory -Force | Out-Null
$config = Join-Path $root 'infrastructure/.env'
$before = [IO.File]::ReadAllBytes($config)
$beforeText = [Text.Encoding]::UTF8.GetString($before)
if ($beforeText -match '(?m)^KYRION_CORE_ADDRESS=') { throw 'EXISTING_BIND_OVERRIDE_REQUIRES_REVIEW' }
[IO.File]::WriteAllBytes((Join-Path $directory 'configuration.env.backup'), $before)
$copy = Join-Path $directory 'core-runtime.jar'
Copy-Item -LiteralPath $review.artifact -Destination $copy
if ((Get-FileHash -LiteralPath $copy -Algorithm SHA256).Hash -ne $review.artifactSha256) { throw 'CORE_ARTIFACT_CHANGED' }
function Start-ReviewedCore([string]$Executable, [string]$Artifact, [string]$Bind, [string]$LogName) {
    $saved = $env:KYRION_CORE_ADDRESS
    try {
        $env:KYRION_CORE_ADDRESS = $Bind
        Start-Process -FilePath $Executable -ArgumentList @('-jar', ('"' + $Artifact + '"')) -WorkingDirectory (Join-Path $root 'services/core') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $directory "$LogName.out.log") -RedirectStandardError (Join-Path $directory "$LogName.err.log") -PassThru
    } finally { $env:KYRION_CORE_ADDRESS = $saved }
}
function Wait-CoreHealth($Process) {
    $deadline = (Get-Date).AddSeconds(90)
    while ((Get-Date) -lt $deadline) {
        if ($Process.HasExited) { throw 'CORE_EXITED' }
        try { if ((Invoke-RestMethod 'http://127.0.0.1:8080/actuator/health' -TimeoutSec 2).status -eq 'UP') { return } } catch { }
        Start-Sleep -Seconds 1
    }
    throw 'CORE_HEALTH_DEADLINE'
}
$stopped = $false
$launched = $null
try {
    & taskkill.exe /PID $CoreProcessId /T /F
    if ($LASTEXITCODE -ne 0) { throw 'CORE_STOP_FAILED' }
    $stopped = $true
    $launched = Start-ReviewedCore $java $copy '0.0.0.0' 'core-lan'
    Wait-CoreHealth $launched
    & (Join-Path $PSScriptRoot 'Probe-PiCore.ps1')
    if ($LASTEXITCODE -ne 0) { throw 'PI_CORE_ACCEPTANCE_FAILED' }
    & node.exe (Join-Path $root 'infrastructure/dev-stack.mjs') status
    if ($LASTEXITCODE -ne 0) { throw 'LOCAL_STACK_ACCEPTANCE_FAILED' }
    # Scope the bind to this verified executable. The existing recovery helper
    # may launch a different Java; a global .env override would evade these
    # program-scoped guards on a later start. Default restarts stay on loopback.
    @{activated=$true; coreProcessId=$launched.Id; artifact=$copy; artifactSha256=$review.artifactSha256; java=$java; configurationKey='KYRION_CORE_ADDRESS'; configurationScope='process-only'; bind='0.0.0.0'; coreAndPiHealthy=$true; guardNames=$names; rollbackJava=$originalJava; rollbackArtifact=$review.artifact} | ConvertTo-Json | Tee-Object -FilePath (Join-Path $directory 'result.json')
} catch {
    $failure = $_.Exception.Message
    if ($launched -and !$launched.HasExited) { Stop-Process -Id $launched.Id -ErrorAction Stop }
    if ($stopped) {
        # The shared configuration is never modified by this activation.
        $rollback = Start-ReviewedCore $originalJava $review.artifact '127.0.0.1' 'core-rollback'
        Wait-CoreHealth $rollback
    }
    @{activated=$false; rollbackPerformed=$stopped; code=$failure} | ConvertTo-Json | Set-Content (Join-Path $directory 'result.json')
    throw "CORE_LAN_ROLLED_BACK: $failure"
}
