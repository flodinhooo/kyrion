param([Parameter(Mandatory=$true)][ValidateSet('plan-create','root-only','verify','grant')][string]$Action)
$ErrorActionPreference='Stop'
[Console]::InputEncoding=New-Object Text.UTF8Encoding($false)
[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
try {
    . (Join-Path $PSScriptRoot 'windows-task-security.ps1')
    $raw=[Console]::In.ReadToEnd()
    if ($raw.Length -gt 32768) { throw 'E_NATIVE_INPUT' }
    $inputData=$raw | ConvertFrom-Json
    $root=[IO.Path]::GetFullPath([string]$inputData.target)
    if ($root -cne [string]$inputData.target -or $root -notmatch '^[A-Za-z]:\\[^\r\n%"<>|?*]+\\[^\r\n%"<>|?*]+$') { throw 'E_NATIVE_TARGET' }
    $parent=Get-Item -LiteralPath ([IO.Path]::GetDirectoryName($root)) -Force
    while ($parent) {
        if ($parent.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'E_NATIVE_REPARSE' }
        Assert-KyrionTaskAncestor (Get-Acl -LiteralPath $parent.FullName)
        $parent=$parent.Parent
    }
    $administrators=New-Object Security.Principal.SecurityIdentifier('S-1-5-32-544')
    $system=New-Object Security.Principal.SecurityIdentifier('S-1-5-18')
    function New-DirectoryPolicy($Readers,$Writers) {
        $acl=New-Object Security.AccessControl.DirectorySecurity
        $acl.SetOwner($administrators)
        $acl.SetAccessRuleProtection($true,$false)
        foreach ($sid in @($administrators,$system)) {
            $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($sid,'FullControl','ContainerInherit,ObjectInherit','None','Allow')))
        }
        foreach ($sid in $Readers) {
            $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($sid,'ReadAndExecute','ContainerInherit,ObjectInherit','None','Allow')))
        }
        foreach ($sid in $Writers) {
            $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($sid,'Modify','ContainerInherit,ObjectInherit','None','Allow')))
        }
        return $acl
    }
    function Assert-Protected($Path,[bool]$RequireProtection=$false) {
        $item=Get-Item -LiteralPath $Path -Force
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'E_NATIVE_REPARSE' }
        $acl=Get-Acl -LiteralPath $Path
        if (($RequireProtection -and -not $acl.AreAccessRulesProtected) -or
            $acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -notin @('S-1-5-18','S-1-5-32-544')) { throw 'E_NATIVE_OWNER' }
        foreach ($rule in $acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])) {
            if ($rule.AccessControlType -eq 'Allow' -and
                $rule.IdentityReference.Value -notin @('S-1-5-18','S-1-5-32-544') -and
                (($rule.IdentityReference.Value -notmatch '^S-1-5-80-[0-9-]+$') -or ([int64]$rule.FileSystemRights -band 0xD0156))) { throw 'E_NATIVE_ACL' }
        }
    }
    if ($Action -ne 'verify') {
        $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
        $principal=New-Object Security.Principal.WindowsPrincipal($identity)
        if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'E_NATIVE_ELEVATION' }
    }
    if ($Action -eq 'plan-create') {
        if (Test-Path -LiteralPath $root) { throw 'E_NATIVE_EXISTING' }
        # Actual exclusive creation uses the installer's typed Win32 call with
        # its fixed private descriptor; no privileged dynamic C# compiler runs.
    } elseif ($Action -eq 'root-only') {
        Assert-Protected $root $true
        if (Test-Path -LiteralPath (Join-Path $root 'install-state.json')) { Assert-Protected (Join-Path $root 'install-state.json') }
    } else {
        Assert-Protected $root $true
        $journalPath=Join-Path $root 'install-state.json'
        $journalFile=Get-Item -LiteralPath $journalPath -Force
        if ($journalFile.Length -gt 1048576 -or ($journalFile.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'E_NATIVE_JOURNAL' }
        $state=Get-Content -LiteralPath $journalPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($state.formatVersion -ne 1 -or $state.backend -ne 'windows-native' -or
            $state.installationId -cnotmatch '^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$' -or
            [IO.Path]::GetFullPath($state.rootPath) -ine $root -or $state.files.'installer.exe' -notmatch '^[a-f0-9]{64}$') { throw 'E_NATIVE_JOURNAL' }
        Assert-Protected $journalPath
        $executable=Join-Path $root 'installer.exe'
        Assert-Protected $executable
        if ((Get-FileHash -LiteralPath $executable -Algorithm SHA256).Hash.ToLowerInvariant() -cne $state.files.'installer.exe') { throw 'E_NATIVE_INTEGRITY' }
        if ($Action -eq 'grant') {
            $sids=@{}
            foreach ($role in @('postgres','core','web','caddy')) {
                $account=New-Object Security.Principal.NTAccount('NT SERVICE',('Kyrion-'+$state.installationId+'-'+$role))
                $sid=$account.Translate([Security.Principal.SecurityIdentifier])
                if ($sid.Value -notmatch '^S-1-5-80-[0-9-]+$') { throw 'E_NATIVE_IDENTITY' }
                $sids[$role]=$sid
            }
            $all=@($sids.postgres,$sids.core,$sids.web,$sids.caddy)
            $rootAcl=New-DirectoryPolicy @() @()
            foreach ($sid in $all) { $rootAcl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($sid,'ReadAndExecute','Allow'))) }
            Set-Acl -LiteralPath $root -AclObject $rootAcl
            foreach ($leaf in @('installer.exe','install-state.json','native-runtime.json','native-manifest.json','core-cert.pem','web-cert.pem','data/Caddyfile')) {
                $fileAcl=New-Object Security.AccessControl.FileSecurity
                $fileAcl.SetOwner($administrators); $fileAcl.SetAccessRuleProtection($true,$false)
                foreach ($sid in @($administrators,$system)) { $fileAcl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($sid,'FullControl','Allow'))) }
                foreach ($sid in $all) { $fileAcl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($sid,'ReadAndExecute','Allow'))) }
                Set-Acl -LiteralPath (Join-Path $root $leaf) -AclObject $fileAcl
            }
            # initdb can create files under its restricted launching-user token.
            # Transfer ownership before the dedicated database identity starts.
            $databasePath=Join-Path $root 'data/postgres'
            foreach ($entry in @(Get-Item -LiteralPath $databasePath -Force) + @(Get-ChildItem -LiteralPath $databasePath -Recurse -Force)) {
                if ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'E_NATIVE_REPARSE' }
                $acl=Get-Acl -LiteralPath $entry.FullName
                $acl.SetOwner($administrators)
                Set-Acl -LiteralPath $entry.FullName -AclObject $acl
            }
            foreach ($row in @(
                @{path='payload'; read=$all; write=@()},
                @{path='secrets'; read=@($sids.core); write=@()},
                @{path='data'; read=@(); write=@()},
                @{path='data/postgres'; read=@(); write=@($sids.postgres)},
                @{path='data/postgres-init'; read=@(); write=@($sids.postgres)},
                @{path='data/core'; read=@(); write=@($sids.core)},
                @{path='data/knowledge'; read=@(); write=@($sids.core)},
                @{path='data/web'; read=@(); write=@($sids.web)},
                @{path='data/caddy'; read=@(); write=@($sids.caddy)},
                @{path='data/web-tls'; read=@($sids.web); write=@()},
                @{path='data/tls'; read=@($sids.caddy); write=@()}
            )) {
                $path=Join-Path $root $row.path
                $item=Get-Item -LiteralPath $path -Force
                if (-not $item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'E_NATIVE_REPARSE' }
                $acl=New-DirectoryPolicy $row.read $row.write
                if ($row.path -eq 'data') {
                    foreach ($sid in $all) { $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($sid,'ReadAndExecute','Allow'))) }
                }
                Set-Acl -LiteralPath $path -AclObject $acl
            }
            $passwordPath=Join-Path $root 'secrets/postgres-password'
            $passwordAcl=New-Object Security.AccessControl.FileSecurity
            $passwordAcl.SetOwner($administrators);$passwordAcl.SetAccessRuleProtection($true,$false)
            foreach ($sid in @($administrators,$system)) { $passwordAcl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($sid,'FullControl','Allow'))) }
            $passwordAcl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($sids.core,'Read','Allow')))
            if ($state.nativeDatabase -ne 'initialized') {
                $passwordAcl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($sids.postgres,'Read','Allow')))
                $secretsPath=Join-Path $root 'secrets'
                $secretsAcl=Get-Acl -LiteralPath $secretsPath
                $secretsAcl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($sids.postgres,'ReadAndExecute','Allow')))
                Set-Acl -LiteralPath $secretsPath -AclObject $secretsAcl
                if ($state.nativeDatabasePending -notmatch '^postgres-pending-[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$') { throw 'E_NATIVE_DATABASE_STATE' }
                $pendingPath=Join-Path (Join-Path $root 'data') $state.nativeDatabasePending
                $pendingItem=Get-Item -LiteralPath $pendingPath -Force
                if (-not $pendingItem.PSIsContainer -or ($pendingItem.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'E_NATIVE_REPARSE' }
                Set-Acl -LiteralPath $pendingPath -AclObject (New-DirectoryPolicy @() @($sids.postgres))
            }
            Set-Acl -LiteralPath $passwordPath -AclObject $passwordAcl

        }
    }
    @{action=$Action; protected=$true} | ConvertTo-Json -Compress
} catch {
    $code=[string]$_.Exception.Message
    if ($code -cmatch '^E_(NATIVE|TASK)_[A-Z_]{1,60}$') { [Console]::Error.WriteLine($code) }
    else { [Console]::Error.WriteLine('E_NATIVE_SECURITY') }
    exit 2
}
