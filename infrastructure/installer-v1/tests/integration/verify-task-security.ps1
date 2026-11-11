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
Write-Output '{"nativeDescriptorsChecked":12,"tasksRegistered":false}'
