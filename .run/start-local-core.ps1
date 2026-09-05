$ErrorActionPreference = 'Stop'
Set-Location 'E:\dev\Kyrion\kyrion'
foreach ($line in Get-Content 'infrastructure\.env') {
    if ($line -match '^([A-Z_]+)=(.*)$') {
        $key = $Matches[1]
        $value = $Matches[2].Trim().Trim('"').Trim("'")
        if ($key -like 'KYRION_SPOTIFY_*') { [Environment]::SetEnvironmentVariable($key, $value, 'Process') }
        if ($key -eq 'KYRION_POSTGRES_PASSWORD') { $env:KYRION_DATABASE_PASSWORD = $value }
        if ($key -eq 'KYRION_POSTGRES_USER') { $env:KYRION_DATABASE_USER = $value }
        if ($key -eq 'KYRION_POSTGRES_DB') { $env:KYRION_DATABASE_URL = "jdbc:postgresql://127.0.0.1:5432/$value" }
    }
}
$env:KYRION_CORE_ADDRESS = '0.0.0.0'
Set-Location 'services\core'
& .\gradlew.bat bootRun
