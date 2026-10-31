function Assert-CoreLanGuards {
    param([Parameter(Mandatory=$true)][string]$Root)
    $java = (Resolve-Path (Join-Path $Root '.run/dev-recovery/toolchain/jdk-21.0.13.0.2+1/bin/java.exe')).Path
    . (Join-Path $Root 'infrastructure/dev/Install-CoreLanGuards.ps1') | Out-Null
    $names = @('Kyrion-CoreLan-Guard-NonPi-v1','Kyrion-CoreLan-Guard-NonPrivate-v1')
    $ranges = Get-Content (Join-Path $Root 'infrastructure/dev/core-lan-guard-addresses.json') -Raw | ConvertFrom-Json
    foreach ($name in $names) {
        $rule = Get-NetFirewallRule -PolicyStore ActiveStore -Name $name -ErrorAction Stop
        $application = $rule | Get-NetFirewallApplicationFilter
        $port = $rule | Get-NetFirewallPortFilter
        $address = $rule | Get-NetFirewallAddressFilter
        $profile = if ($name -eq $names[0]) { 'Any' } else { 'Domain, Public' }
        $remote = if ($name -eq $names[0]) { $ranges } else { @('Any') }
        if ($rule.Enabled.ToString() -ne 'True' -or $rule.Action.ToString() -ne 'Block' -or
            $rule.Direction.ToString() -ne 'Inbound' -or $rule.PrimaryStatus.ToString() -ne 'OK' -or
            $rule.Profile.ToString() -ne $profile -or $application.Program -ine $java -or
            $port.Protocol -ne 'TCP' -or $port.LocalPort -ne '8080' -or
            (Compare-Object @($address.RemoteAddress | ForEach-Object { ConvertTo-CoreFirewallAddress $_ } | Sort-Object) `
                @($remote | ForEach-Object { ConvertTo-CoreFirewallAddress $_ } | Sort-Object))) {
            throw 'EFFECTIVE_FIREWALL_GUARD_MISMATCH'
        }
    }
    $allow = Get-NetFirewallRule -PolicyStore ActiveStore -DisplayName 'Kyrion Core from kyrion-node' -ErrorAction Stop
    $allowPort = $allow | Get-NetFirewallPortFilter
    $allowAddress = $allow | Get-NetFirewallAddressFilter
    if ($allow.Enabled.ToString() -ne 'True' -or $allow.Action.ToString() -ne 'Allow' -or
        $allow.Direction.ToString() -ne 'Inbound' -or $allow.Profile.ToString() -ne 'Private' -or
        $allowPort.Protocol -ne 'TCP' -or $allowPort.LocalPort -ne '8080' -or
        (Compare-Object @($allowAddress.RemoteAddress | Sort-Object) @('192.168.1.115','192.168.1.116'))) {
        throw 'EXISTING_SCOPED_FIREWALL_RULE_MISMATCH'
    }
    if (!(Get-NetConnectionProfile | Where-Object NetworkCategory -eq 'Private') -or
        (Get-NetFirewallProfile -PolicyStore ActiveStore | Where-Object {
            $_.Enabled.ToString() -ne 'True' -or $_.DefaultInboundAction.ToString() -ne 'Block'
        })) { throw 'FIREWALL_DISABLED_OR_UNSAFE' }
    return $java
}

function Read-CoreLanManifest {
    param([string]$Root, [string]$Manifest)
    $value = Get-Content -LiteralPath $Manifest -Raw | ConvertFrom-Json
    if ($value.version -isnot [int] -or $value.version -ne 1 -or $value.artifact -isnot [string] -or
        $value.artifactSha256 -isnot [string] -or $value.artifactSha256 -notmatch '^[a-fA-F0-9]{64}$' -or
        @($value.PSObject.Properties.Name | Where-Object { $_ -notin @('version','artifact','artifactSha256') }).Count) {
        throw 'INVALID_CORE_LAN_MANIFEST'
    }
    $artifact = (Resolve-Path -LiteralPath $value.artifact).Path
    $runtime = (Resolve-Path (Join-Path $Root '.run/dev-recovery')).Path
    if (!$artifact.StartsWith($runtime + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -or
        (Get-FileHash -LiteralPath $artifact -Algorithm SHA256).Hash -ine $value.artifactSha256) {
        throw 'PINNED_CORE_ARTIFACT_MISMATCH'
    }
    return $value
}
