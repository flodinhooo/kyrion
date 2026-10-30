[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][int]$CoreProcessId,
    [switch]$Apply
)
$ErrorActionPreference = 'Stop'
$sourceRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$process = Get-CimInstance Win32_Process -Filter "ProcessId=$CoreProcessId"
if (!$process -or $process.Name -ne 'java.exe') { throw 'CORE_PROCESS_IDENTITY_MISMATCH' }
$match = [regex]::Match($process.CommandLine, '-jar\s+(?:"([^"]+)"|(\S+))')
$artifact = if ($match.Groups[1].Success) { $match.Groups[1].Value } else { $match.Groups[2].Value }
if (!$artifact) { throw 'CORE_JAR_NOT_IDENTIFIED' }
$artifact = (Resolve-Path -LiteralPath $artifact).Path
$runtimeRoot = (Resolve-Path (Join-Path $sourceRoot '.run/dev-recovery')).Path
if (!$artifact.StartsWith($runtimeRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'CORE_ARTIFACT_OUTSIDE_REVIEWED_RUNTIME'
}
$children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$CoreProcessId")
$consoleHost = Join-Path $env:WINDIR 'System32/conhost.exe'
if ($children | Where-Object {
    !(($_.Name -eq 'java.exe' -and $_.CommandLine.Contains($artifact)) -or
      ($_.Name -eq 'conhost.exe' -and $_.ExecutablePath -ieq $consoleHost))
}) {
    throw 'CORE_HAS_UNREVIEWED_CHILDREN'
}
$rule = Get-NetFirewallRule -DisplayName 'Kyrion Core from kyrion-node'
$ports = $rule | Get-NetFirewallPortFilter
$addresses = @($rule | Get-NetFirewallAddressFilter | Select-Object -ExpandProperty RemoteAddress)
$expectedAddresses = @('192.168.1.115', '192.168.1.116')
if ($rule.Enabled -ne 'True' -or $rule.Action -ne 'Allow' -or $rule.Direction -ne 'Inbound' -or
    $rule.Profile.ToString() -ne 'Private' -or $ports.Protocol -ne 'TCP' -or $ports.LocalPort -ne '8080' -or
    (Compare-Object ($addresses | Sort-Object) ($expectedAddresses | Sort-Object))) {
    throw 'EXISTING_SCOPED_FIREWALL_RULE_MISMATCH'
}
if (!(Get-NetConnectionProfile | Where-Object NetworkCategory -eq 'Private') -or
    (Get-NetFirewallProfile -Name Private).Enabled -ne 'True') { throw 'PRIVATE_FIREWALL_REQUIRED' }
$config = Join-Path $sourceRoot 'infrastructure/.env'
$bytes = [IO.File]::ReadAllBytes($config)
$configHash = (Get-FileHash -LiteralPath $config -Algorithm SHA256).Hash
$text = [Text.Encoding]::UTF8.GetString($bytes)
$configured = [regex]::Match($text, '(?m)^KYRION_CORE_ADDRESS=([^\r\n]*)')
if ($configured.Success -and $configured.Groups[1].Value -ne '0.0.0.0') { throw 'EXISTING_BIND_OVERRIDE_REQUIRES_REVIEW' }
$plan = [ordered]@{
    processId = $CoreProcessId; childProcessIds = @($children.ProcessId)
    processCreated = $process.CreationDate.ToString('o'); artifact = $artifact
    artifactSha256 = (Get-FileHash -LiteralPath $artifact -Algorithm SHA256).Hash
    configurationKey = 'KYRION_CORE_ADDRESS'; bind = '0.0.0.0'; port = 8080
    allowedRemoteAddresses = $addresses; firewallChanges = $false
    scope = 'Only the identified Core Java tree; preserve its exact JAR and all other services'
    apply = [bool]$Apply
}
if (!$Apply) { [pscustomobject]$plan | ConvertTo-Json; return }

# Apply only after explicit operator authorization of the displayed network scope.
$current = Get-CimInstance Win32_Process -Filter "ProcessId=$CoreProcessId"
if (!$current -or $current.CreationDate -ne $process.CreationDate) { throw 'CORE_PROCESS_CHANGED' }
$java = if ($env:JAVA_HOME) { Join-Path $env:JAVA_HOME 'bin/java.exe' } else { (Get-Command java.exe).Source }
if (!(Test-Path -LiteralPath $java)) { throw 'JAVA_RUNTIME_MISSING' }
$directory = Join-Path $runtimeRoot 'sprint03'
New-Item -ItemType Directory -Force -Path $directory | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$copy = Join-Path $directory "core-lan-$stamp.jar"
Copy-Item -LiteralPath $artifact -Destination $copy
if (!$configured.Success) {
    if ((Get-FileHash -LiteralPath $config -Algorithm SHA256).Hash -ne $configHash) { throw 'CONFIGURATION_CHANGED' }
    $newline = if ($text.EndsWith("`n")) { '' } else { "`r`n" }
    $suffix = [Text.Encoding]::UTF8.GetBytes($newline + "KYRION_CORE_ADDRESS=0.0.0.0`r`n")
    [IO.File]::WriteAllBytes($config, [byte[]]($bytes + $suffix))
}
& taskkill.exe /PID $CoreProcessId /T /F
if ($LASTEXITCODE -ne 0) { throw 'CORE_STOP_FAILED_CONFIGURATION_RETAINED' }
$savedBind = $env:KYRION_CORE_ADDRESS
try {
    $env:KYRION_CORE_ADDRESS = '0.0.0.0'
    $launched = Start-Process -FilePath $java -ArgumentList @('-jar', "`"$copy`"") -WorkingDirectory (Join-Path $sourceRoot 'services/core') -WindowStyle Hidden -RedirectStandardOutput "$directory/core-$stamp.out.log" -RedirectStandardError "$directory/core-$stamp.err.log" -PassThru
    $plan['newProcessId'] = $launched.Id
    $plan['runtimeCopy'] = $copy
    $ready = $false
    $deadline = (Get-Date).AddSeconds(90)
    while ((Get-Date) -lt $deadline) {
        if ($launched.HasExited) { throw 'CORE_EXITED_DURING_LAN_START' }
        try {
            $health = Invoke-RestMethod 'http://127.0.0.1:8080/actuator/health' -TimeoutSec 2
            if ($health.status -eq 'UP') { $ready = $true; break }
        } catch { }
        Start-Sleep -Seconds 1
    }
    $plan['coreReady'] = $ready
    [pscustomobject]$plan | ConvertTo-Json | Set-Content -LiteralPath "$directory/core-launch-$stamp.json" -Encoding UTF8
    [pscustomobject]$plan | ConvertTo-Json
    if (!$ready) { throw 'CORE_NOT_READY_INSPECT_PRIVATE_STARTUP_LOGS' }
} finally { $env:KYRION_CORE_ADDRESS = $savedBind }
