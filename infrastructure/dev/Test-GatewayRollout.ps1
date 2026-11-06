[CmdletBinding()]
param(
    [string]$JavaHome = $env:JAVA_HOME,
    [switch]$FullCoreSuite
)

# Isolated acceptance only. No live URLs, DB credentials, restore targets or device IDs accepted.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$coordination = Join-Path $root '.run/dev-recovery/coordination'
$outputDirectory = Join-Path $root ('.run/dev-recovery/gateway-acceptance/' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $coordination, $outputDirectory -Force | Out-Null
$report = [ordered]@{ format = 'kyrion-gateway-acceptance-v1'; passed = $false; schemaRehearsalTarget = 43;
    rolloutAuthorized = $false; mode = $(if ($FullCoreSuite) { 'full-core' } else { 'gateway' }); startedAt = [DateTime]::UtcNow.ToString('o') }
$heldLock = $null
$savedJavaHome = $env:JAVA_HOME
$exitCode = 1

function Get-CoreSourceHashes {
    $hashes = [ordered]@{}
    $paths = @(Get-ChildItem (Join-Path $root 'services/core/src') -Recurse -File | Select-Object -ExpandProperty FullName)
    $paths += Join-Path $root 'services/core/build.gradle.kts'
    $paths += Join-Path $root 'services/core/settings.gradle.kts'
    foreach ($path in ($paths | Sort-Object)) {
        $relative = $path.Substring($root.Length + 1).Replace('\', '/')
        $hashes[$relative] = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    return $hashes
}

try {
    if (!$JavaHome -or !(Test-Path -LiteralPath (Join-Path $JavaHome 'bin/java.exe'))) { throw 'JDK_21_REQUIRED' }
    $heldLock = [IO.File]::Open((Join-Path $coordination 'core-checks.lock'), [IO.FileMode]::OpenOrCreate,
        [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
    $env:JAVA_HOME = $JavaHome
    $savedErrorAction = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $javaVersion = (& (Join-Path $JavaHome 'bin/java.exe') -version 2>&1 | Out-String)
        $javaExit = $LASTEXITCODE
    } finally { $ErrorActionPreference = $savedErrorAction }
    if ($javaExit -ne 0 -or $javaVersion -notmatch 'version "21[.+-]') { throw 'JDK_21_REQUIRED' }
    $report.javaMajor = 21
    $report.headBefore = (& git -C $root rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'GIT_HEAD_FAILED' }
    $before = Get-CoreSourceHashes
    $before | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $outputDirectory 'source-before.json') -Encoding UTF8
    $arguments = @('test')
    if (!$FullCoreSuite) {
        $arguments += @('--tests', 'dev.kyrion.core.security.GatewayAuthorityIntegrationTest',
            '--tests', 'dev.kyrion.core.security.GatewayRolloutRehearsalTest')
    }
    $arguments += @('bootJar', '--console=plain', '--rerun-tasks')
    Push-Location (Join-Path $root 'services/core')
    $savedErrorAction = $ErrorActionPreference
    try {
        # PowerShell 5 treats native stderr warnings as ErrorRecords; use the native exit code.
        $ErrorActionPreference = 'Continue'
        & .\gradlew.bat @arguments *> (Join-Path $outputDirectory 'gradle.log')
        $report.gradleExitCode = $LASTEXITCODE
    } finally { $ErrorActionPreference = $savedErrorAction; Pop-Location }
    $after = Get-CoreSourceHashes
    $after | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $outputDirectory 'source-after.json') -Encoding UTF8
    $changed = @(@($before.Keys) + @($after.Keys) | Sort-Object -Unique | Where-Object { $before[$_] -ne $after[$_] })
    $report.changedCoreSources = $changed
    $report.headAfter = (& git -C $root rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'GIT_HEAD_FAILED' }
    if ($report.gradleExitCode -ne 0) { throw 'GRADLE_FAILED' }
    if ($changed.Count) { throw 'CORE_CHANGED_DURING_CHECKS' }
    $totals = [ordered]@{ tests = 0; failures = 0; errors = 0; skipped = 0 }
    $suites = [ordered]@{}
    foreach ($file in Get-ChildItem (Join-Path $root 'services/core/build/test-results/test') -Filter 'TEST-*.xml') {
        $xml = [xml](Get-Content $file.FullName -Raw)
        $suites[$xml.testsuite.name] = [int]$xml.testsuite.tests
        foreach ($key in @('tests', 'failures', 'errors', 'skipped')) { $totals[$key] += [int]$xml.testsuite.$key }
    }
    $report.tests = $totals
    $report.suites = $suites
    if ($totals.failures -or $totals.errors -or $totals.skipped -or
        $suites['dev.kyrion.core.security.GatewayAuthorityIntegrationTest'] -lt 28 -or
        $suites['dev.kyrion.core.security.GatewayRolloutRehearsalTest'] -lt 1) { throw 'REQUIRED_ACCEPTANCE_MISSING' }
    $jar = Join-Path $root 'services/core/build/libs/kyrion-core-0.1.0-SNAPSHOT.jar'
    $report.artifactSha256 = (Get-FileHash -LiteralPath $jar -Algorithm SHA256).Hash.ToLowerInvariant()
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [IO.Compression.ZipFile]::OpenRead($jar)
    try {
        $report.artifactMigrations = @($archive.Entries | ForEach-Object {
            if ($_.FullName -match '^BOOT-INF/classes/db/migration/V([0-9]+)__') { [int]$matches[1] }
        } | Sort-Object)
    } finally { $archive.Dispose() }
    if (42 -notin $report.artifactMigrations -or 43 -notin $report.artifactMigrations) { throw 'ARTIFACT_MIGRATION_CATALOG_INCOMPLETE' }
    $report.artifactMigrationsBeyondRehearsal = @($report.artifactMigrations | Where-Object { $_ -gt 43 })
    $report.passed = $true
    $exitCode = 0
} catch {
    $report.error = $_.Exception.Message
} finally {
    if ($heldLock) { $heldLock.Dispose() }
    $env:JAVA_HOME = $savedJavaHome
    $report.finishedAt = [DateTime]::UtcNow.ToString('o')
    $report | ConvertTo-Json -Depth 8 | Set-Content (Join-Path $outputDirectory 'evidence.json') -Encoding UTF8
    Write-Output $outputDirectory
}
exit $exitCode
