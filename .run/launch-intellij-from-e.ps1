$ErrorActionPreference = 'Stop'

$ideaProcess = Get-Process -Name 'idea64' -ErrorAction SilentlyContinue
if ($ideaProcess) {
    Write-Host 'IntelliJ is still running. Close all IntelliJ windows and run this launcher again.'
    Read-Host 'Press Enter to close'
    exit 1
}

$localSource = 'C:\Users\Flo\AppData\Local\JetBrains\IntelliJIdea2026.2'
$localTarget = 'E:\DevData\JetBrains\Local\IntelliJIdea2026.2'
$configSource = 'C:\Users\Flo\AppData\Roaming\JetBrains\IntelliJIdea2026.2'
$configTarget = 'E:\DevData\JetBrains\Roaming\IntelliJIdea2026.2'
$ideaExecutable = 'E:\DevTools\JetBrains\IntelliJ IDEA\bin\idea64.exe'
$propertiesFile = 'E:\DevData\JetBrains\idea-e.properties'

function Move-DirectoryToE {
    param(
        [Parameter(Mandatory)] [string] $Source,
        [Parameter(Mandatory)] [string] $Target
    )

    $backup = "$Source.pre-e-drive-backup"
    $sourceItem = Get-Item -LiteralPath $Source -ErrorAction SilentlyContinue
    if ($sourceItem -and $sourceItem.LinkType -eq 'Junction') {
        Write-Host "Already redirected: $Source"
        return
    }
    if (-not $sourceItem) {
        if (Test-Path -LiteralPath $backup) {
            New-Item -ItemType Junction -Path $Source -Target $Target | Out-Null
            return
        }
        Write-Host "Skipped missing directory: $Source"
        return
    }
    if (Test-Path -LiteralPath $backup) {
        throw "A previous backup already exists: $backup"
    }

    New-Item -ItemType Directory -Path $Target -Force | Out-Null
    & robocopy $Source $Target /E /COPY:DAT /DCOPY:DAT /R:2 /W:1 /XJ /NFL /NDL /NP /NJH /NJS
    if ($LASTEXITCODE -gt 7) {
        throw "Synchronization failed with code $LASTEXITCODE for $Source."
    }

    $sourceBytes = (Get-ChildItem -LiteralPath $Source -File -Recurse -Force | Measure-Object Length -Sum).Sum
    $targetBytes = (Get-ChildItem -LiteralPath $Target -File -Recurse -Force | Measure-Object Length -Sum).Sum
    if ($targetBytes -lt $sourceBytes) {
        throw "Target is smaller than source for $Source."
    }

    Rename-Item -LiteralPath $Source -NewName (Split-Path -Leaf $backup)
    New-Item -ItemType Junction -Path $Source -Target $Target | Out-Null
    Write-Host "Redirected to E: $Source -> $Target"
}

foreach ($path in @($localTarget, $configTarget)) {
    New-Item -ItemType Directory -Path $path -Force | Out-Null
}

& robocopy $localSource $localTarget /E /COPY:DAT /DCOPY:DAT /R:2 /W:1 /XJ /NFL /NDL /NP /NJH /NJS
if ($LASTEXITCODE -gt 7) {
    throw "Local JetBrains data synchronization failed with code $LASTEXITCODE."
}

& robocopy $configSource $configTarget /E /COPY:DAT /DCOPY:DAT /R:2 /W:1 /XJ /NFL /NDL /NP /NJH /NJS
if ($LASTEXITCODE -gt 7) {
    throw "JetBrains configuration synchronization failed with code $LASTEXITCODE."
}

$properties = @'
idea.config.path=E:/DevData/JetBrains/Roaming/IntelliJIdea2026.2
idea.system.path=E:/DevData/JetBrains/Local/IntelliJIdea2026.2
idea.plugins.path=E:/DevData/JetBrains/Roaming/IntelliJIdea2026.2/plugins
idea.log.path=E:/DevData/JetBrains/Local/IntelliJIdea2026.2/log
'@
[System.IO.File]::WriteAllText($propertiesFile, $properties, [System.Text.UTF8Encoding]::new($false))

# Stop background build daemons before relocating their cache.
& 'E:\dev\Kyrion\kyrion\services\core\gradlew.bat' --stop 2>$null

Move-DirectoryToE -Source 'C:\Users\Flo\curseforge' -Target 'E:\Games\CurseForge'
Move-DirectoryToE -Source 'C:\Users\Flo\AppData\Local\Android\Sdk' -Target 'E:\DevTools\Android\Sdk'
Move-DirectoryToE -Source 'C:\Users\Flo\.gradle' -Target 'E:\DevData\Caches\Gradle'
Move-DirectoryToE -Source 'C:\Users\Flo\AppData\Local\npm-cache' -Target 'E:\DevData\Caches\npm'
Move-DirectoryToE -Source 'C:\Users\Flo\AppData\Local\pnpm-cache' -Target 'E:\DevData\Caches\pnpm'
Move-DirectoryToE -Source 'C:\Users\Flo\AppData\Local\pnpm' -Target 'E:\DevTools\pnpm'

[Environment]::SetEnvironmentVariable('ANDROID_HOME', 'E:\DevTools\Android\Sdk', 'User')
[Environment]::SetEnvironmentVariable('ANDROID_SDK_ROOT', 'E:\DevTools\Android\Sdk', 'User')
[Environment]::SetEnvironmentVariable('GRADLE_USER_HOME', 'E:\DevData\Caches\Gradle', 'User')
[Environment]::SetEnvironmentVariable('NPM_CONFIG_CACHE', 'E:\DevData\Caches\npm', 'User')
[Environment]::SetEnvironmentVariable('PNPM_HOME', 'E:\DevTools\pnpm', 'User')

$env:ANDROID_HOME = 'E:\DevTools\Android\Sdk'
$env:ANDROID_SDK_ROOT = 'E:\DevTools\Android\Sdk'
$env:GRADLE_USER_HOME = 'E:\DevData\Caches\Gradle'
$env:NPM_CONFIG_CACHE = 'E:\DevData\Caches\npm'
$env:PNPM_HOME = 'E:\DevTools\pnpm'

if (-not (Test-Path -LiteralPath $ideaExecutable)) {
    throw "The staged IntelliJ executable was not found: $ideaExecutable"
}

$env:IDEA_PROPERTIES = $propertiesFile
Start-Process -FilePath $ideaExecutable -WorkingDirectory 'E:\dev\Kyrion\kyrion'

Write-Host 'IntelliJ was started from E:. Keep the C: originals until the new installation is verified.'
