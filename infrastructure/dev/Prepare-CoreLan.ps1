[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
# Preparation only: never changes a listener, firewall, interface, DNS or process.
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$config = Join-Path $root 'infrastructure/.env'
$directory = Join-Path $root ('.run/dev-recovery/sprint04/' + [guid]::NewGuid().ToString())
$bytes = [IO.File]::ReadAllBytes($config)
$hash = [Security.Cryptography.SHA256]::Create()
try { $before = ([BitConverter]::ToString($hash.ComputeHash($bytes))).Replace('-', '') }
finally { $hash.Dispose() }
New-Item -ItemType Directory -Path $directory -Force | Out-Null
# Private local recovery material; never print its content or copy it into docs.
$backup = Join-Path $directory 'configuration.env.backup'
[IO.File]::WriteAllBytes($backup, $bytes)
if ((Get-FileHash -LiteralPath $backup -Algorithm SHA256).Hash -ne $before) {
    throw 'CONFIGURATION_BACKUP_MISMATCH'
}
$listeners = @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
    Where-Object LocalPort -eq 8080 | Select-Object LocalAddress,LocalPort,OwningProcess)
$interfaces = @(Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.IPAddress -notmatch '^(127\.|169\.254\.)' } |
    Select-Object InterfaceAlias,IPAddress)
$rule = Get-NetFirewallRule -DisplayName 'Kyrion Core from kyrion-node'
$ports = $rule | Get-NetFirewallPortFilter
$addresses = $rule | Get-NetFirewallAddressFilter
$profiles = @(Get-NetFirewallProfile -PolicyStore ActiveStore |
    Select-Object Name,@{Name='Enabled';Expression={$_.Enabled.ToString()}},@{Name='DefaultInboundAction';Expression={$_.DefaultInboundAction.ToString()}})
$javaCandidate = Join-Path $root '.run/dev-recovery/toolchain/jdk-21.0.13.0.2+1/bin/java.exe'
$plan = [ordered]@{
    preparedAt = (Get-Date).ToString('o')
    activated = $false
    configurationUnchanged = ((Get-FileHash -LiteralPath $config -Algorithm SHA256).Hash -eq $before)
    backup = $backup
    backupSha256 = $before
    listeners = $listeners
    interfaces = $interfaces
    firewall = @{
        name = $rule.DisplayName; enabled = $rule.Enabled.ToString()
        profile = $rule.Profile.ToString(); action = $rule.Action.ToString()
        protocol = $ports.Protocol; port = $ports.LocalPort
        remoteAddresses = $addresses.RemoteAddress
    }
    firewallProfiles = $profiles
    candidateBind = '0.0.0.0'
    candidateJava = $javaCandidate
    candidateJavaPresent = (Test-Path -LiteralPath $javaCandidate)
    currentJavaRuleWarning = 'The existing JDK22 Allow rule permits any source/port in Private; do not reuse that executable for LAN activation'
    proposedFirewallGuards = @(
        @{action='Block'; program=$javaCandidate; protocol='TCP'; localPort=8080; profile='Any'; remoteAddresses=@('0.0.0.0-126.255.255.255','128.0.0.0-192.168.1.114','192.168.1.117-255.255.255.255','::/0')},
        @{action='Block'; program=$javaCandidate; protocol='TCP'; localPort=8080; profile='Public,Domain'; remoteAddresses=@('Any')}
    )
    reason = 'Retains existing 127.0.0.1 clients and adds IPv4 LAN; single Spring listener cannot bind two individual addresses'
    activationBlocked = @(
        'Explicit operator approval required',
        'Review overlapping Allow rules for the exact Java executable, port ranges and all profiles',
        'Re-identify current Core artifact/process and validate installed migrations',
        'Verify rollback launch and all service readiness before scheduling interruption'
    )
    rollback = 'Stop only the newly launched Core; restore only KYRION_CORE_ADDRESS if configuration changed; restart the identical JAR with bind 127.0.0.1; verify localhost health. Never overwrite concurrent .env changes.'
    piChanges = $false
    dnsChanges = $false
}
if (!$plan.configurationUnchanged) { throw 'CONFIGURATION_CHANGED_DURING_PREPARATION' }
$json = $plan | ConvertTo-Json -Depth 6
$json | Set-Content -LiteralPath (Join-Path $directory 'plan.json') -Encoding UTF8
$json
