$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '../../windows-task-security.ps1')
Assert-KyrionTaskSecurityDescriptor $KyrionTaskSecurityDescriptor
# Windows can expand GENERIC_ALL to the concrete file/task rights mask.
Assert-KyrionTaskSecurityDescriptor 'O:SYG:SYD:P(A;;FA;;;SY)(A;;FA;;;BA)'
$invalid = @(
    'O:LSG:BAD:P(A;;GA;;;SY)(A;;GA;;;BA)',
    'O:BAG:BAD:(A;;GA;;;SY)(A;;GA;;;BA)',
    'O:BAG:BAD:P(A;;GA;;;SY)(A;;GA;;;LS)',
    'O:BAG:BAD:P(A;;GA;;;SY)(A;;GA;;;BA)(A;;GR;;;BU)',
    'O:BAG:BAD:P(A;;GA;;;SY)(A;;GR;;;BA)',
    'O:BAG:BAD:P(A;;GA;;;SY)(A;;GA;;;SY)',
    'O:BAG:BAD:P(D;;GA;;;SY)(A;;GA;;;BA)',
    'O:BAG:BAD:P(A;ID;GA;;;SY)(A;;GA;;;BA)',
    'O:BAG:BAD:NO_ACCESS_CONTROL',
    'invalid-sddl'
)
foreach ($candidate in $invalid) {
    $rejected = $false
    try { Assert-KyrionTaskSecurityDescriptor $candidate }
    catch { if ($_.Exception.Message -cne 'E_TASK_SECURITY') { throw }; $rejected = $true }
    if (-not $rejected) { throw 'E_TEST_TASK_SECURITY_ACCEPTED' }
}
function New-TestAncestor([string]$Owner,[Security.AccessControl.FileSystemRights]$Rights) {
    $acl = New-Object Security.AccessControl.DirectorySecurity
    $acl.SetOwner((New-Object Security.Principal.SecurityIdentifier($Owner)))
    $acl.SetAccessRuleProtection($true,$false)
    $users = New-Object Security.Principal.SecurityIdentifier('S-1-5-32-545')
    $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($users,$Rights,'Allow')))
    return $acl
}
Assert-KyrionTaskAncestor (New-TestAncestor 'S-1-5-32-544' 'ReadAndExecute')
Assert-KyrionTaskAncestor (New-TestAncestor 'S-1-5-18' 'AppendData')
foreach ($rights in @('WriteData','DeleteSubdirectoriesAndFiles','Delete','ChangePermissions','TakeOwnership')) {
    $rejected = $false
    try { Assert-KyrionTaskAncestor (New-TestAncestor 'S-1-5-32-544' $rights) }
    catch { if ($_.Exception.Message -cne 'E_TASK_ANCESTOR') { throw }; $rejected = $true }
    if (-not $rejected) { throw 'E_TEST_ANCESTOR_ACCEPTED' }
}
$rejected = $false
try { Assert-KyrionTaskAncestor (New-TestAncestor 'S-1-5-32-545' 'ReadAndExecute') }
catch { if ($_.Exception.Message -cne 'E_TASK_ANCESTOR') { throw }; $rejected = $true }
if (-not $rejected) { throw 'E_TEST_ANCESTOR_OWNER' }
Write-Output '{"nativeDescriptorsChecked":12,"ancestorPoliciesChecked":8,"tasksRegistered":false}'
