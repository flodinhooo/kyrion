# Fixed task policy: only administrators and System may change/run managed tasks.
$KyrionTaskSecurityDescriptor = 'O:BAG:BAD:P(A;;GA;;;SY)(A;;GA;;;BA)'
function Assert-KyrionTaskSecurityDescriptor([string]$Sddl) {
    try { $security = New-Object Security.AccessControl.RawSecurityDescriptor($Sddl) }
    catch { throw 'E_TASK_SECURITY' }
    if ($security.Owner.Value -notin @('S-1-5-18','S-1-5-32-544') -or
        -not ($security.ControlFlags -band [Security.AccessControl.ControlFlags]::DiscretionaryAclProtected) -or
        $null -eq $security.DiscretionaryAcl -or $security.DiscretionaryAcl.Count -ne 2) { throw 'E_TASK_SECURITY' }
    $identities = @()
    foreach ($ace in $security.DiscretionaryAcl) {
        if ($ace -isnot [Security.AccessControl.CommonAce] -or
            $ace.AceQualifier -ne [Security.AccessControl.AceQualifier]::AccessAllowed -or
            $ace.AceFlags -ne [Security.AccessControl.AceFlags]::None -or $ace.IsCallback -or
            $ace.SecurityIdentifier.Value -notin @('S-1-5-18','S-1-5-32-544') -or
            -not (($ace.AccessMask -band 0x10000000) -or (($ace.AccessMask -band 0x1F01FF) -eq 0x1F01FF))) {
            throw 'E_TASK_SECURITY'
        }
        $identities += $ace.SecurityIdentifier.Value
    }
    if (@($identities | Select-Object -Unique).Count -ne 2) { throw 'E_TASK_SECURITY' }
}

# A protected leaf is insufficient beneath a user-replaceable ancestor.
function Assert-KyrionTaskAncestor($Acl) {
    $trusted = @('S-1-5-18','S-1-5-32-544')
    try {
        $installerAccount = New-Object Security.Principal.NTAccount('NT SERVICE','TrustedInstaller')
        $trusted += $installerAccount.Translate([Security.Principal.SecurityIdentifier]).Value
    } catch { } # Unknown optional platform identity never broadens trust.
    if ($Acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -notin $trusted) { throw 'E_TASK_ANCESTOR' }
    foreach ($rule in $Acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])) {
        if ($rule.AccessControlType -ne [Security.AccessControl.AccessControlType]::Allow -or
            ($rule.PropagationFlags -band [Security.AccessControl.PropagationFlags]::InheritOnly)) { continue }
        if ($rule.IdentityReference.Value -in $trusted) { continue }
        # Generic write/all, write-data/reparse, delete-child, delete, write-DACL,
        # or write-owner permit replacing a trusted descendant. Directory-create
        # alone is allowed (ProgramData); exclusive creation refuses prior data.
        if ([int64]$rule.FileSystemRights -band 0x500D0042) { throw 'E_TASK_ANCESTOR' }
    }
}
