[CmdletBinding()]
param(
    [string]$ConfigRoot,
    [string]$JavaHome = $env:JAVA_HOME,
    [int]$CorePort = 8080,
    [int]$WebPort = 3000,
    [ValidateSet('All','Core','Web')][string]$Mode = 'All',
    [string]$LogDirectory = (Join-Path $env:TEMP 'kyrion-recovery-development')
)
$ErrorActionPreference = 'Stop'
$sourceRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
if (!$ConfigRoot) {
    $commonGit = (& git -C $sourceRoot rev-parse --path-format=absolute --git-common-dir).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Cannot discover the primary checkout. Pass -ConfigRoot explicitly.' }
    $ConfigRoot = Split-Path $commonGit -Parent
}
$ConfigRoot = (Resolve-Path -LiteralPath $ConfigRoot).Path
$coreConfig = Join-Path $ConfigRoot 'infrastructure/.env'
if (!(Test-Path -LiteralPath $coreConfig)) { throw 'The selected configuration root has no infrastructure/.env. Existing configuration was not changed.' }
$java = if ($JavaHome) { Join-Path $JavaHome 'bin/java.exe' } else { (Get-Command java.exe).Source }
if (!(Test-Path -LiteralPath $java)) { throw 'Java executable missing. Pass -JavaHome pointing to an existing JDK 21 or newer.' }
$jar = Join-Path $sourceRoot 'services/core/build/libs/kyrion-core-0.1.0-SNAPSHOT.jar'
if (!(Test-Path -LiteralPath $jar)) { throw 'Build Core with gradlew.bat bootJar before starting this script.' }
$jarTime = (Get-Item -LiteralPath $jar).LastWriteTimeUtc
if (Get-ChildItem (Join-Path $sourceRoot 'services/core/src/main') -Recurse -File | Where-Object LastWriteTimeUtc -gt $jarTime) {
    throw 'Core sources are newer than the JAR. Rebuild bootJar before starting.'
}
$ports = @()
if ($Mode -ne 'Web') { $ports += $CorePort }
if ($Mode -ne 'Core') { $ports += $WebPort }
foreach ($port in $ports) {
    if (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue) {
        throw "Port $port is in use. Inspect the owning process before stopping it; this script never replaces running services."
    }
}
$node = (Get-Command node.exe).Source
$next = Join-Path $sourceRoot 'apps/web/node_modules/next/dist/bin/next'
if (!(Test-Path -LiteralPath $next)) { throw 'Install the existing Web lockfile dependencies before starting.' }
New-Item -ItemType Directory -Force -Path $LogDirectory | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$savedEnvironment = @{}
foreach ($key in @('SPRING_CONFIG_IMPORT','CORE_SERVICE_URL','KYRION_PUBLIC_URL','KYRION_WEB_CONFIG_FILE')) { $savedEnvironment[$key] = [Environment]::GetEnvironmentVariable($key,'Process') }
try {
    # Import the original configuration without copying secrets into a worktree.
    $env:SPRING_CONFIG_IMPORT = 'optional:file:' + $coreConfig.Replace([char]92,[char]47) + '[.properties]'
    $env:CORE_SERVICE_URL = "http://127.0.0.1:$CorePort"
    $env:KYRION_PUBLIC_URL = "http://localhost:$WebPort"
    $runtimeJar = $null
    if ($Mode -ne 'Web') {
        $runtimeJar = Join-Path $LogDirectory "core-$stamp.jar"
        # Build output may change during development; execute an immutable copy.
        Copy-Item -LiteralPath $jar -Destination $runtimeJar
        $core = Start-Process -FilePath $java -ArgumentList @('-jar', "`"$runtimeJar`"", "--server.port=$CorePort", '--server.address=127.0.0.1') -WorkingDirectory (Join-Path $sourceRoot 'services/core') -WindowStyle Hidden -RedirectStandardOutput "$LogDirectory/core-$stamp.out.log" -RedirectStandardError "$LogDirectory/core-$stamp.err.log" -PassThru
    } else { $core = Get-Process -Id (Get-NetTCPConnection -State Listen -LocalPort $CorePort | Select-Object -First 1 -ExpandProperty OwningProcess) }
    $healthy = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        if ($core.HasExited) { throw 'Core exited during startup. Inspect its local logs; Web was not started.' }
        try { $health = Invoke-RestMethod "http://127.0.0.1:$CorePort/actuator/health" -TimeoutSec 2; if ($health.status -eq 'UP') { $healthy = $true; break } } catch { }
        Start-Sleep -Seconds 1
    }
    if (!$healthy) { throw 'Core is not healthy yet. Inspect its logs before starting Web.' }
    if ($Mode -ne 'Core') {
    $webArguments = @()
    $webConfig = Join-Path $ConfigRoot 'apps/web/.env.local'
    if (Test-Path -LiteralPath $webConfig) { $env:KYRION_WEB_CONFIG_FILE = $webConfig }
    $webArguments += @('--require', "`"$(Join-Path $PSScriptRoot 'web-env.cjs')`"")
    $webArguments += @("`"$next`"", 'dev', '--port', "$WebPort", '--hostname', '127.0.0.1')
    $web = Start-Process -FilePath $node -ArgumentList $webArguments -WorkingDirectory (Join-Path $sourceRoot 'apps/web') -WindowStyle Hidden -RedirectStandardOutput "$LogDirectory/web-$stamp.out.log" -RedirectStandardError "$LogDirectory/web-$stamp.err.log" -PassThru
    $webReady = $false
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        if ($web.HasExited) { throw 'Web exited during startup. Core remains running; inspect the Web logs.' }
        if (Get-NetTCPConnection -State Listen -LocalPort $WebPort -ErrorAction SilentlyContinue) { $webReady = $true; break }
        Start-Sleep -Milliseconds 500
    }
    if (!$webReady) { throw 'Web did not open its port. Inspect the local Web logs.' }
    } else {
        $webListener = Get-NetTCPConnection -State Listen -LocalPort $WebPort -ErrorAction SilentlyContinue | Select-Object -First 1
        $web = if ($webListener) { Get-Process -Id $webListener.OwningProcess } else { $null }
    }
    $manifest = [ordered]@{ sourceRoot=$sourceRoot; configurationRoot=$ConfigRoot; branch=(& git -C $sourceRoot branch --show-current).Trim(); jarSha256=$(if ($runtimeJar) { (Get-FileHash -LiteralPath $runtimeJar -Algorithm SHA256).Hash } else { $null }); runtimeJar=$runtimeJar; corePid=$core.Id; webPid=$web.Id; corePort=$CorePort; webPort=$WebPort; startedAt=(Get-Date).ToString('o') }
    $manifest | ConvertTo-Json | Set-Content -LiteralPath "$LogDirectory/launch-$stamp.json" -Encoding UTF8
    [pscustomobject]$manifest
} finally {
    foreach ($key in $savedEnvironment.Keys) { [Environment]::SetEnvironmentVariable($key,$savedEnvironment[$key],'Process') }
}
