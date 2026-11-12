param([Parameter(Mandatory=$true)][string]$LiteralPath, [switch]$Directory)
$ErrorActionPreference = 'Stop'
try {
    $item = Get-Item -LiteralPath $LiteralPath -Force
    if ($item.PSIsContainer -ne $Directory.IsPresent -or
        ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { exit 1 }
    $acl = Get-Acl -LiteralPath $LiteralPath
    $operatorSid = [Security.Principal.WindowsIdentity]::GetCurrent().User
    if (!$acl.AreAccessRulesProtected -or $acl.Access.Count -ne 1 -or
        $acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -ne $operatorSid.Value) { exit 1 }
    $rule = $acl.Access[0]
    $inheritance = if ($Directory) { 3 } else { 0 }
    $full = [Security.AccessControl.FileSystemRights]::FullControl
    if ($rule.IsInherited -or $rule.AccessControlType -ne 'Allow' -or
        $rule.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value -ne $operatorSid.Value -or
        ($rule.FileSystemRights -band $full) -ne $full -or
        [int]$rule.InheritanceFlags -ne $inheritance -or [int]$rule.PropagationFlags -ne 0) { exit 1 }
    exit 0
} catch { exit 2 }
