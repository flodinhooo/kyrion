# Web pre-image review — 2026-09-05

Status: ready for owner review of the local Web application. No container
image was built, exported or installed during this review. The Pi was only
queried through read-only SSH and HTTP checks.

## Resulting behavior

- Home is the default landing page; Chat is second in navigation and owns
  conversation history. Ordinary platform pages do not request AI status,
  model catalogs or conversation history. Model settings remain an explicit
  exception for the catalog.
- Desktop and narrow layouts retain reachable navigation, scrolling dialogs,
  readable action controls and keyboard focus. The skip link moves focus into
  the main workspace. Home links on Activity, Settings and Profile now have
  matching labels instead of claiming to open Chat.
- Login and first-owner setup use German/English resources, preserve the
  selected language and show actionable network/Core failures. Core identity
  requests time out after five seconds; authentication submission is bounded.
- Core unavailability is a 503, not an expired-session 401. Open pages check
  session validity on focus and every minute; confirmed expiry offers sign-in.
- Failed room writes remain visible in their dialog. Device management restores
  pending controls after failures. Home/Device requests have bounded duration
  and never automatically replay commands whose outcome is unknown.
- Blocked browser preference storage and missing browser speech synthesis do
  not stop the ordinary workspace from loading.
- Web Docker inputs exclude local `.env` files, generated Next environments,
  normal/review build output and review artifacts. The isolated review build
  does not require changes to runtime dependencies or production settings.

## Verification

| Check | Result |
| --- | --- |
| Web unit tests | 74 passed |
| Web ESLint | Passed |
| Next production build and TypeScript | Passed, `.next-review` output |
| Browser route/layout matrix and interactions | 115 passed |
| Final targeted browser interactions after the optional-speech fix | 13 passed |
| Core tests, including PostgreSQL/Testcontainers | 144 passed, none skipped |
| Core executable JAR | Built successfully |
| AI service tests | 114 passed |
| Gateway agent tests | 17 passed; one Linux-only metrics test skipped on Windows |
| Voice Satellite tests | 50 passed |
| Docker/Buildx/Compose source preflight | Passed |
| Local Web/Core/AI/Ollama/STT HTTP checks | All returned 200; PostgreSQL healthy |
| Existing Pi read-only checks | ARM64, about 38 GB free; Docker and gateway service active; Core health UP; Web login 200 |

The browser matrix covers 17 routes at 1440, 390 and 320 pixels in both light
and dark themes. AI is unreachable for the entire run. The real Web server
uses a separate loopback fixture Core; room and device mutations affect only
temporary fixture memory. Five secondary endpoints (activity integrity,
personal memory, retention, sessions and the fixture health endpoint) return
explicit failure fixtures, so their pages are checked in degraded states.
They are not a claim of successful real-account testing. There were no
unhandled browser exceptions.

Browser reproduction instructions are in
[`apps/web/scripts/README.md`](../../apps/web/scripts/README.md). Local evidence
is stored under `.run/release-review/browser/results.json` and
`results-quick.json`, alongside viewport screenshots. Core XML reports are
under `.run/release-review/core-build-isolated/test-results/test`. These
generated artifacts are deliberately ignored by Git.

## Owner review

Open `http://localhost:3000` and review the final appearance, room/device
management, Lounge and Chat. Physical light changes and Spotify receiver
playback still require owner observation with the real installation; the
automated review does not claim those physical outcomes. This is the owner's
requested review gate before building the next image, not another feature phase.

## Next prompt: image/update handoff

This is an update of the existing Pi platform, **not a first migration**.
Do not rerun `install-platform.sh` or copy the development database over the
Pi database. Keep `/etc/kyrion/platform/platform.env`, TLS configuration,
`/var/lib/kyrion/postgres`, credential and audit keys, radio data and service
enrolments on the Pi.

1. Record the exact reviewed source revision and rerun
   `infrastructure/nodes/kyrion-node/check-platform-update.ps1`.
2. In the separately authorized image task, build Core and Web for
   `linux/arm64` from `services/core` and `apps/web`, using explicit versioned
   image tags. No AI image is required for the always-on platform.
3. Before activation, retain the running image tags/configuration and make a
   protected Pi database backup with the existing key backup. Existing
   privileged deployment access is required; this review did not read
   root-only configuration or use sudo credentials.
4. Load/update only the intended images and start Core/Web against the existing
   Pi environment and persistent paths. Inspect any new Flyway migrations
   before activation; database rollback is separate from image rollback.
5. Verify HTTPS login, Core health, room/device reads, one owner-observed light
   operation and receiver playback where configured. Repeat basic device
   control with AI unreachable. A new image's ARM64 runtime can only be
   verified after that image exists.

No production dependency was added for browser automation. No formatter is
configured in the Web package; ESLint and `git diff --check` were used.
