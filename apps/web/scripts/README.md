# Browser review

`review-browser.mjs` exercises the real production Web build against a
loopback-only fixture Core. AI is deliberately unreachable. No real owner
credentials, devices, rooms or external provider accounts are used. Fixture
mutations live only in memory and disappear when the process exits.

Install the review-only driver from the repository root (it does not change
the application's dependencies):

```powershell
npm install --prefix .run/browser-review --no-save --package-lock=false playwright-core@1.63.0
```

Then, from `apps/web`:

```powershell
$env:KYRION_BUILD_DIRECTORY = '.next-review'
pnpm build
$env:REVIEW_PLAYWRIGHT_PATH = (Resolve-Path '../../.run/browser-review/node_modules/playwright-core').Path
node scripts/review-browser.mjs
```

The script uses installed Chrome on Windows. Set `REVIEW_BROWSER` to another
Chromium executable if needed. Port 3107 is reserved for the temporary Web
server; `REVIEW_WEB_PORT` overrides it. The fixture Core uses a random loopback
port. Both are stopped in `finally`. Output is stored under
`.run/release-review/browser`, outside Docker build inputs.

The full run checks 17 routes at 1440, 390 and 320 pixels, light and dark
themes, absence of unwanted AI/history requests, horizontal overflow, mobile
menu focus, room creation, device filtering and commands, offline recovery,
failed writes, expired sessions, login localization and network errors,
keyboard skip navigation and blocked browser storage. Secondary APIs without
a fixture return explicit 503 responses, exercising those pages' error states;
they are listed in `unexpectedFixtureRequests` in the report. This is not
physical-device, Spotify-account or screen-reader acceptance.

`REVIEW_QUICK=1` runs only the interaction/failure checks after a targeted fix
and writes `results-quick.json`, preserving the full `results.json` report.
Screenshots are viewport captures; review long pages by scrolling the live app.
