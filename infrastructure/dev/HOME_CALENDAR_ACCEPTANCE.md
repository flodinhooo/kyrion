# Isolated authenticated HOME/calendar browser checks

Opt-in software acceptance for KY-001, not a personal-installation updater.
The runner starts the actual packaged Core, a production Web build and a new
PostgreSQL database. It sends no invitations and uses no external provider.

Prerequisites: Java 21, local Docker Desktop with an already available
`postgres:17-alpine` image, Node/pnpm, and the repository's existing Website
development dependencies (`pg`, Playwright and installed Chromium). No new
dependency or download is performed by the runner. Windows/Docker Desktop is the
verified host; other host platforms are not certified by this result.

Prepare a separate Web source copy using `git archive HEAD apps/web` (not a Git
worktree). Install with its frozen lockfile and build **inside that copy**.
Do not copy private `.env` files. Use an existing reviewed Core boot JAR with its
matching SHA-256; no Core rebuild is needed when its main source is unchanged.
The runner refuses the ordinary `apps/web` directory, private Web environment
files, mismatching tracked Web inputs, an unreviewed JAR hash or remote Docker.

From the repository root, substitute the reviewed paths/hash:

```text
node infrastructure/dev/home-calendar-acceptance.mjs --web-directory <separate-built-Web-source-copy> --java-home <JDK21> --core-jar <reviewed-Core-JAR> --core-sha256 <SHA256>
```

The runner selects free loopback ports, creates new random fixture keys/passwords
and a unique temporary PostgreSQL container with tmpfs data. It resolves the
existing PostgreSQL image to its immutable local image ID rather than pulling
an update. It copies the reviewed JAR into a fresh working directory and strips
inherited application settings. Personal `.env`, keys and databases are not used.
It never mounts a Docker socket. External Java HTTP(S) is directed to a denying
loopback proxy; browser requests outside the fixture origin are rejected.

The first synthetic HOME owner is created through real Core bootstrap. Additional
synthetic member accounts/roles are seeded only in that new database, using the
fixture password hash; there is no invitation or session fabrication. All tested
sessions subsequently log in through the actual Web password form. Roles include
a fully privileged calendar nonparticipant and an account with no calendar rights.

`home-calendar-browser-checks.mjs` executes four DE/EN desktop/mobile scenarios:
explicit participation, joint edits, a real stale-revision 409 with exact error
code and fully visible translated feedback, creator-only delete, HTTP 403/401
denials, actual audit actors and independent logout. It never fulfills a fake
HTTP response; its fetch observer clones the application's real mutation replies
inside Chromium to avoid a CDP response-body retrieval error.

Results, source/artifact hashes and synthetic screenshots go to a unique ignored
`.run/private-evidence/ky001-*` directory. Credentials are not printed; do not
commit that directory. On success/failure the runner stops only its own child
processes and named fixture container; tmpfs database data is discarded. A failure
or unexpected outbound request returns nonzero. Readiness retries are bounded;
an interrupted runner is not proof of successful acceptance.

The [manual personal-installation checklist](../../docs/home-family-calendar-manual-acceptance.md)
remains a separate gate. Provider consent/delivery, actual phones and real-user
acceptance are outside this software-only fixture.
