[CmdletBinding()]
param([switch]$Apply)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$java = (Resolve-Path (Join-Path $root '.run/dev-recovery/toolchain/jdk-21.0.13.0.2+1/bin/java.exe')).Path
$ranges = (Get-Content (Join-Path $PSScriptRoot 'core-lan-guard-addresses.json') -Raw | ConvertFrom-Json)
$specs = @(
    @{Name='Kyrion-CoreLan-Guard-NonPi-v1'; Profile='Any'; RemoteAddress=$ranges},
    @{Name='Kyrion-CoreLan-Guard-NonPrivate-v1'; Profile=@('Public','Domain'); RemoteAddress=@('Any')}
)
if (!$Apply) {
    @{applied=$false; program=$java; port=8080; rules=$specs} | ConvertTo-Json -Depth 5
    return
}
# This switch is an operator command, not an authorization bypass. Sprint 04
# explicitly authorized only these two guards; no existing rule is edited.
$created = @()
try {
    if (![Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'FIREWALL_ADMINISTRATOR_TOKEN_REQUIRED'
    }
    foreach ($spec in $specs) {
        if (Get-NetFirewallRule -Name $spec.Name -ErrorAction SilentlyContinue) {
            throw 'GUARD_NAME_ALREADY_EXISTS_REVIEW_REQUIRED'
        }
        New-NetFirewallRule -PolicyStore PersistentStore -Name $spec.Name -DisplayName $spec.Name -Direction Inbound -Action Block -Enabled True -Profile $spec.Profile -Program $java -Protocol TCP -LocalPort 8080 -RemoteAddress $spec.RemoteAddress -ErrorAction Stop | Out-Null
        $created += $spec.Name
    }
    foreach ($spec in $specs) {
        $rule = Get-NetFirewallRule -PolicyStore ActiveStore -Name $spec.Name -ErrorAction Stop
        $application = $rule | Get-NetFirewallApplicationFilter
        $port = $rule | Get-NetFirewallPortFilter
        $address = $rule | Get-NetFirewallAddressFilter
        $expectedProfile = if ($spec.Profile -eq 'Any') { 'Any' } else { 'Domain, Public' }
        if ($rule.Enabled.ToString() -ne 'True' -or $rule.Action.ToString() -ne 'Block' -or
            $rule.Direction.ToString() -ne 'Inbound' -or $rule.Profile.ToString() -ne $expectedProfile -or
            $application.Program -ine $java -or $port.Protocol -ne 'TCP' -or $port.LocalPort -ne '8080' -or
            (Compare-Object @($address.RemoteAddress | ForEach-Object { $_ -replace '/32$', '' } | Sort-Object) @($spec.RemoteAddress | ForEach-Object { $_ -replace '/32$', '' } | Sort-Object))) {
            throw 'EFFECTIVE_GUARD_SCOPE_MISMATCH'
        }
    }
    $profiles = Get-NetFirewallProfile -PolicyStore ActiveStore
    if ($profiles | Where-Object { $_.Enabled.ToString() -ne 'True' -or $_.DefaultInboundAction.ToString() -ne 'Block' }) {
        throw 'EFFECTIVE_FIREWALL_PROFILE_MISMATCH'
    }
    @{applied=$true; program=$java; port=8080; effectiveRulesVerified=$true; createdNames=$created} | ConvertTo-Json
} catch {
    foreach ($name in $created) { Remove-NetFirewallRule -PolicyStore PersistentStore -Name $name -ErrorAction Stop }
    throw
}
