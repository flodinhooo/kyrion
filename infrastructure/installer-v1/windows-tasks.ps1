param([Parameter(Mandatory=$true)][ValidateSet('validate','inspect','register','start','stop','remove')][string]$Action)
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
try {
    . (Join-Path $PSScriptRoot 'windows-task-security.ps1')
    Assert-KyrionTaskSecurityDescriptor $KyrionTaskSecurityDescriptor
    $raw = [Console]::In.ReadToEnd()
    if ($raw.Length -gt 32768) { throw 'E_TASK_INPUT' }
    $plan = $raw | ConvertFrom-Json
    if ($plan.name -notmatch '^Kyrion-[a-f0-9-]{36}-(core|web|caddy|updates)$') { throw 'E_TASK_NAME' }
    $isUpdate = $plan.name.EndsWith('-updates')
    $principalSid = 'S-1-5-19'
    $bootDelay = 'PT30S'
    $executionLimit = 'PT0S'
    $workerFile = 'installer.exe'
    if ($isUpdate) {
        $principalSid = 'S-1-5-18'
        $bootDelay = 'PT2M'
        $executionLimit = 'PT10M'
        $updateInterval = 'PT24H'
        $approvedXml = [xml]$plan.xml
        if ([string]$approvedXml.Task.Settings.ExecutionTimeLimit -eq 'PT2H') {
            $executionLimit = 'PT2H'
            $updateInterval = 'PT1H'
        }
        $workerFile = [IO.Path]::GetFileName([string]$plan.command)
        if ($workerFile -cnotmatch '^maintenance-[a-f0-9]{32}\.exe$' -or
            [IO.Path]::Combine([string]$plan.directory, $workerFile) -cne $plan.command) { throw 'E_TASK_EXECUTABLE' }
    }
    $scheduler = New-Object -ComObject 'Schedule.Service'
    $scheduler.Connect()
    $definition = $scheduler.NewTask(0)
    $definition.XmlText = [string]$plan.xml
    $definition.Principal.LogonType = 5

    function Assert-Definition($candidate) {
        [xml]$candidateXml = $candidate.XmlText
        if ($isUpdate) {
            if ($candidateXml.Task.Principals.Principal.ProcessTokenSidType -and
                $candidateXml.Task.Principals.Principal.ProcessTokenSidType -ne 'Default') { throw 'E_TASK_TOKEN' }
        } elseif ($candidateXml.Task.Principals.Principal.ProcessTokenSidType -ne 'Unrestricted') { throw 'E_TASK_TOKEN' }
        if ($isUpdate) {
            if ($candidate.Triggers.Item(1).Repetition.Interval -ne $updateInterval -or
                $candidate.Triggers.Item(1).Repetition.Duration -or
                $candidate.Triggers.Item(1).Repetition.StopAtDurationEnd) { throw 'E_TASK_INTERVAL' }
        } elseif ($candidate.Triggers.Item(1).Repetition.Interval) { throw 'E_TASK_INTERVAL' }
        if ($candidate.Actions.Count -ne 1 -or $candidate.Actions.Item(1).Type -ne 0 -or
            $candidate.Actions.Item(1).Path -cne $plan.command -or
            $candidate.Actions.Item(1).Arguments -cne $plan.arguments -or
            $candidate.Actions.Item(1).WorkingDirectory -cne $plan.directory -or
            $candidate.RegistrationInfo.Description -cne $plan.description -or
            $candidate.Triggers.Count -ne 1 -or $candidate.Triggers.Item(1).Type -ne 8 -or
            $candidate.Triggers.Item(1).Delay -ne $bootDelay -or -not $candidate.Triggers.Item(1).Enabled -or
            $candidate.Principal.LogonType -ne 5 -or $candidate.Principal.RunLevel -ne 0 -or
            $candidate.Settings.MultipleInstances -ne 2 -or $candidate.Settings.RestartCount -ne 3 -or
            $candidate.Settings.RestartInterval -ne 'PT1M' -or $candidate.Settings.ExecutionTimeLimit -ne $executionLimit -or
            -not $candidate.Settings.Enabled -or -not $candidate.Settings.StartWhenAvailable -or
            -not $candidate.Settings.Hidden -or -not $candidate.Settings.AllowHardTerminate -or
            -not $candidate.Settings.AllowDemandStart -or $candidate.Settings.RunOnlyIfIdle -or
            $candidate.Settings.DisallowStartIfOnBatteries -or $candidate.Settings.StopIfGoingOnBatteries -or
            $candidate.Settings.RunOnlyIfNetworkAvailable -or $candidate.Settings.WakeToRun) { throw 'E_TASK_OWNERSHIP' }
        $principalId = [string]$candidate.Principal.UserId
        if ($principalId -like 'S-1-*') { $sid = New-Object System.Security.Principal.SecurityIdentifier($principalId) }
        else { $account = New-Object System.Security.Principal.NTAccount($principalId); $sid = $account.Translate([System.Security.Principal.SecurityIdentifier]) }
        if ($sid.Value -ne $principalSid) { throw 'E_TASK_PRINCIPAL' }
    }
    Assert-Definition $definition
    if ($Action -in @('register','start','stop','remove')) {
        # Mutations require an owned native installation, not just a matching
        # task name. The service account must never be able to rewrite these
        # administrator-owned inputs consumed by an elevated installer.
        $directory = Get-Item -LiteralPath $plan.directory -Force
        $parent = $directory
        while ($parent) {
            if ($parent.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'E_TASK_TARGET' }
            if ($parent.FullName -ine $directory.FullName) {
                Assert-KyrionTaskAncestor (Get-Acl -LiteralPath $parent.FullName)
            }
            $parent = $parent.Parent
        }
        $journalPath = Join-Path $directory.FullName 'install-state.json'
        $journalFile = Get-Item -LiteralPath $journalPath -Force
        if ($journalFile.Length -gt 1048576 -or ($journalFile.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'E_TASK_JOURNAL' }
        $journal = Get-Content -LiteralPath $journalPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($journal.formatVersion -ne 1 -or $journal.backend -ne 'windows-native' -or
            $plan.name -cne ('Kyrion-' + $journal.installationId + '-' + ($plan.name -split '-')[-1]) -or
            [IO.Path]::GetFullPath($journal.rootPath) -ine $directory.FullName -or
            $journal.files.$workerFile -notmatch '^[a-f0-9]{64}$') { throw 'E_TASK_JOURNAL' }
        if ($isUpdate -and ($journal.updatePolicy.workerFile -cne $workerFile -or
            ('maintenance-' + $journal.files.$workerFile.Substring(0,32) + '.exe') -cne $workerFile)) { throw 'E_TASK_JOURNAL' }
        foreach ($ownedPath in @($directory.FullName, $journalPath, $plan.command)) {
            $item = Get-Item -LiteralPath $ownedPath -Force
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'E_TASK_TARGET' }
            $acl = Get-Acl -LiteralPath $ownedPath
            if ($acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -notin @('S-1-5-18','S-1-5-32-544')) { throw 'E_TASK_OWNER' }
            if ($ownedPath -eq $directory.FullName -and -not $acl.AreAccessRulesProtected) { throw 'E_TASK_ACL' }
            foreach ($rule in $acl.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier])) {
                if ($rule.AccessControlType -ne [Security.AccessControl.AccessControlType]::Allow) { continue }
                $sid = $rule.IdentityReference.Value
                if ($sid -in @('S-1-5-18','S-1-5-32-544')) { continue }
                if ($sid -notmatch '^S-1-5-(80|87)-[0-9-]+$' -or ([int64]$rule.FileSystemRights -band 0xD0156)) { throw 'E_TASK_ACL' }
            }
        }
        if ((Get-FileHash -LiteralPath $plan.command -Algorithm SHA256).Hash.ToLowerInvariant() -cne $journal.files.$workerFile) { throw 'E_TASK_INTEGRITY' }
    }
    $exists = $false
    $task = $null
    if ($Action -ne 'validate') {
        $folder = $scheduler.GetFolder('\')
        try { $task = $folder.GetTask([string]$plan.name); $exists = $true }
        catch {
            $cause = $_.Exception
            while ($cause.InnerException) { $cause = $cause.InnerException }
            if ($cause.HResult -notin @(-2147024894, -2147024893)) { throw }
        }
        if ($exists) {
            Assert-Definition $task.Definition
            Assert-KyrionTaskSecurityDescriptor ($task.GetSecurityDescriptor(7))
        }
        if ($Action -eq 'register' -and -not $exists) {
            if (-not (Test-Path -LiteralPath $plan.command -PathType Leaf)) { throw 'E_TASK_EXECUTABLE' }
            # TASK_CREATE | TASK_DONT_ADD_PRINCIPAL_ACE: no overwrite, no shared
            # Local Service ACE that could alter the validated task definition.
            $task = $folder.RegisterTaskDefinition([string]$plan.name, $definition, 18, $principalSid, $null, 5, $KyrionTaskSecurityDescriptor)
            Assert-Definition $task.Definition
            Assert-KyrionTaskSecurityDescriptor ($task.GetSecurityDescriptor(7))
            $exists = $true
        }
        if ($Action -eq 'start') { if (-not $exists) { throw 'E_TASK_MISSING' }; $null = $task.Run($null) }
        if ($Action -eq 'stop' -and $exists) { $task.Stop(0) }
        if ($Action -eq 'remove' -and $exists) { $folder.DeleteTask([string]$plan.name, 0); $exists = $false }
    }
    @{ name=$plan.name; action=$Action; definitionValidated=$true; taskSecurityPolicyValidated=$true; registered=$exists; coldBootVerified=$false } | ConvertTo-Json -Compress
} catch {
    # Native errors can contain paths/account metadata. Never emit raw exceptions.
    $code = [string]$_.Exception.Message
    if ($code -cmatch '^E_TASK_[A-Z_]{1,60}$') { [Console]::Error.WriteLine($code) }
    else { [Console]::Error.WriteLine('E_WINDOWS_TASK_NATIVE') }
    exit 2
}
