[CmdletBinding()]
param(
    [string]$JavaHome = $env:JAVA_HOME,
    [string]$Python = 'python',
    [switch]$FullCoreSuite
)

# Synthetic-only runner. No operational connection/settings/dump arguments accepted.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$coordination = Join-Path $root '.run/dev-recovery/coordination'
$outputDirectory = Join-Path $root ('.run/dev-recovery/schema-acceptance/' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $coordination, $outputDirectory -Force | Out-Null
$report = [ordered]@{ format = 'kyrion-schema-acceptance-v1'; passed = $false; target = 46;
    rolloutAuthorized = $false; startedAt = [DateTime]::UtcNow.ToString('o') }
$heldLock = $null
$savedJavaHome = $env:JAVA_HOME
$savedArtifact = $env:KYRION_MIGRATION_REHEARSAL_JAR
$savedPython = $env:KYRION_MIGRATION_PYTHON
$exitCode = 1

function Get-SourceHashes {
    $hashes = [ordered]@{}
    $paths = @(Get-ChildItem (Join-Path $root 'services/core/src') -Recurse -File | Select-Object -ExpandProperty FullName)
    $paths += Join-Path $root 'services/core/build.gradle.kts'
    $paths += Join-Path $root 'services/core/settings.gradle.kts'
    $paths += Join-Path $PSScriptRoot 'CoreSchemaMigration.java'
    $paths += Join-Path $PSScriptRoot 'Migrate-CoreSchema.py'
    foreach ($path in ($paths | Sort-Object)) {
        $hashes[$path.Substring($root.Length + 1).Replace('\', '/')] = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    return $hashes
}

function Invoke-Gradle([string[]]$Arguments, [string]$Log) {
    Push-Location (Join-Path $root 'services/core')
    $savedErrorAction = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & .\gradlew.bat @Arguments *> (Join-Path $outputDirectory $Log)
        if ($LASTEXITCODE -ne 0) { throw 'GRADLE_FAILED' }
    } finally { $ErrorActionPreference = $savedErrorAction; Pop-Location }
}

try {
    if (!$JavaHome -or !(Test-Path -LiteralPath (Join-Path $JavaHome 'bin/java.exe'))) { throw 'JDK_21_REQUIRED' }
    $JavaHome = (Resolve-Path -LiteralPath $JavaHome).Path
    $heldLock = [IO.File]::Open((Join-Path $coordination 'core-checks.lock'), [IO.FileMode]::OpenOrCreate,
        [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
    $env:JAVA_HOME = $JavaHome
    $env:KYRION_MIGRATION_PYTHON = $Python
    $report.headBefore = (& git -C $root rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'GIT_HEAD_FAILED' }
    $before = Get-SourceHashes
    $before | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $outputDirectory 'source-before.json') -Encoding UTF8
    Invoke-Gradle @('bootJar', '--console=plain', '--rerun-tasks') 'build.log'
    $jar = Join-Path $root 'services/core/build/libs/kyrion-core-0.1.0-SNAPSHOT.jar'
    $env:KYRION_MIGRATION_REHEARSAL_JAR = Join-Path $outputDirectory 'reviewed-core.jar'
    Copy-Item -LiteralPath $jar -Destination $env:KYRION_MIGRATION_REHEARSAL_JAR
    $report.artifactSha256 = (Get-FileHash -LiteralPath $env:KYRION_MIGRATION_REHEARSAL_JAR -Algorithm SHA256).Hash.ToLowerInvariant()
    $arguments = @('test')
    if (!$FullCoreSuite) {
        $arguments += @('--tests', 'dev.kyrion.core.security.CoreSchemaMigrationRehearsalTest',
            '--tests', 'dev.kyrion.core.security.GatewayAuthorityIntegrationTest')
    }
    $arguments += @('--console=plain', '--rerun-tasks')
    Invoke-Gradle $arguments 'test.log'
    $totals = [ordered]@{ tests = 0; failures = 0; errors = 0; skipped = 0 }
    $suites = [ordered]@{}
    foreach ($file in Get-ChildItem (Join-Path $root 'services/core/build/test-results/test') -Filter 'TEST-*.xml') {
        $xml = [xml](Get-Content $file.FullName -Raw)
        $suites[$xml.testsuite.name] = [int]$xml.testsuite.tests
        foreach ($key in @('tests', 'failures', 'errors', 'skipped')) { $totals[$key] += [int]$xml.testsuite.$key }
    }
    $report.tests = $totals
    $report.suites = $suites
    if ($totals.failures -or $totals.errors -or ($totals.skipped -ne $(if ($FullCoreSuite) { 1 } else { 0 })) -or
        $suites['dev.kyrion.core.security.CoreSchemaMigrationRehearsalTest'] -lt 6 -or
        $suites['dev.kyrion.core.security.GatewayAuthorityIntegrationTest'] -lt 28) { throw 'REQUIRED_ACCEPTANCE_MISSING' }
    $after = Get-SourceHashes
    $after | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $outputDirectory 'source-after.json') -Encoding UTF8
    $report.changedSources = @(@($before.Keys) + @($after.Keys) | Sort-Object -Unique | Where-Object { $before[$_] -ne $after[$_] })
    if ($report.changedSources.Count) { throw 'SOURCE_CHANGED_DURING_CHECKS' }
    $report.headAfter = (& git -C $root rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'GIT_HEAD_FAILED' }
    if ((Get-FileHash -LiteralPath $env:KYRION_MIGRATION_REHEARSAL_JAR -Algorithm SHA256).Hash.ToLowerInvariant() -ne $report.artifactSha256) { throw 'ARTIFACT_CHANGED' }
    $report.passed = $true
    $exitCode = 0
} catch { $report.error = $_.Exception.Message }
finally {
    if ($heldLock) { $heldLock.Dispose() }
    $env:JAVA_HOME = $savedJavaHome
    $env:KYRION_MIGRATION_REHEARSAL_JAR = $savedArtifact
    $env:KYRION_MIGRATION_PYTHON = $savedPython
    $report.finishedAt = [DateTime]::UtcNow.ToString('o')
    $report | ConvertTo-Json -Depth 8 | Set-Content (Join-Path $outputDirectory 'evidence.json') -Encoding UTF8
    Write-Output $outputDirectory
}
exit $exitCode
