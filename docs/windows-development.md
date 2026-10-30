# Windows development from an isolated worktree

The primary checkout can hold private configuration while a worktree supplies
application code. Do not copy `.env` files into the worktree or run an old JAR
without identifying it. The launcher imports the primary checkout's Core config,
preloads its existing Web `.env.local` using Node's native parser, and sets the
local Core URL explicitly. It never starts/stops PostgreSQL or replaces an occupied
port. This is a Windows PC workflow, not a Raspberry Pi deployment.

## Inspect before starting or replacing anything

```powershell
Set-Location 'E:\dev\Kyrion\kyrion'
git worktree list
git status --short
Get-NetTCPConnection -State Listen |
  Where-Object LocalPort -in 3000, 8080, 5432 |
  Select-Object LocalAddress, LocalPort, OwningProcess
docker ps --format '{{.Names}} {{.Ports}}'
```

Inspect process command lines locally, but never publish them if arguments contain
credentials. Check unsaved source changes, active requests and other development
tasks before stopping only a verified process. No kill-all or automatic restart is
part of the launcher. The services below are already running after acceptance;
do not rerun startup blindly against those ports.

## Build and start

Use an existing JDK 21 for Gradle. In the inspected session it is available under
`$env:TEMP\kyrion-jdk21\Eclipse Adoptium\jdk-21.0.3.9-hotspot`; a permanent installation
may be passed instead. Java 22 alone does not satisfy the configured Gradle 21
toolchain. Docker Desktop must be running for PostgreSQL/Testcontainers. Inspect
Compose status before starting an existing database; never recreate its data.

```powershell
$repo = 'E:\dev\Kyrion\kyrion\.worktrees\calendar-ha-recovery'
Set-Location $repo
$env:JAVA_HOME = Join-Path $env:TEMP 'kyrion-jdk21\Eclipse Adoptium\jdk-21.0.3.9-hotspot'
Push-Location services\core
.\gradlew.bat test bootJar --console=plain
Pop-Location
Push-Location apps\web
pnpm install --frozen-lockfile
pnpm test
pnpm lint
pnpm exec next typegen
pnpm exec tsc --noEmit
Pop-Location
# Only when the selected ports are free:
.\infrastructure\dev\Start-WindowsDevelopment.ps1 `
  -ConfigRoot 'E:\dev\Kyrion\kyrion' -JavaHome $env:JAVA_HOME
```

`-Mode Core` or `-Mode Web` starts only the selected component after its port is
free. The launcher records source/configuration roots, branch, PIDs, startup time
and the Core artifact hash under `%TEMP%\kyrion-recovery-development`. Logs stay
there and contain no emitted configuration values. Core runs an immutable JAR
copy, so rebuilding the worktree cannot replace resources beneath a running JVM.
Web readiness is checked instead of assuming a successfully spawned Node process
will keep running. Next dev cannot safely inherit `--env-file` through its child
`NODE_OPTIONS`; the provided preload avoids that confirmed failure.

Use a separate build directory while dev is serving the application:

```powershell
Push-Location "$repo\apps\web"
$previousBuildDirectory = $env:KYRION_BUILD_DIRECTORY
try {
  $env:KYRION_BUILD_DIRECTORY = '.next-acceptance-build'
  pnpm build
} finally {
  $env:KYRION_BUILD_DIRECTORY = $previousBuildDirectory
  Pop-Location
}
Invoke-RestMethod 'http://127.0.0.1:8080/actuator/health'
Invoke-WebRequest 'http://localhost:3000/login' -UseBasicParsing
```

## Configuration and acceptance

The discovered PostgreSQL service is `kyrion-postgres`, PostgreSQL 17, with a
loopback port at 5432 and the original E: bind mount. An unrelated container on
5433 is outside Kyrion and was left alone. Core and Web bind loopback; LAN gateway
access is not enabled by this launcher. Do not repoint a production gateway at a
development PC just to obtain live state.

Google's configured development callback is
`http://localhost:3000/api/integrations/google/callback`. The inspected stored
refresh token returns `invalid_grant`; the user must reconnect through Google
settings. An authenticated browser session is required for calendar/device UI
acceptance. Never reset an account or manufacture a session to bypass that step.
Calendar scheduling defaults off and may only be enabled by the account holder.

Before migrating the actual local database, a custom-format backup was saved in
`%TEMP%\kyrion-local-acceptance-backups`. These files contain private data and must
remain outside Git. V31's original applied checksum is `1755433543`: its later
format-only source change prevented startup. Restore the historical SQL, not the
database checksum; never apply Flyway repair or disable validation as a workaround.

See the [live acceptance report](status/2026-10-19-windows-live-acceptance.md) for
what was actually verified and what still needs account-holder action.
