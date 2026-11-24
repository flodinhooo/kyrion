# Prepared-node unknown health

ADR 0092 extends the existing gateway health contract, without another device
registry or schema migration. Nullable observations preserve the difference
between unknown and false. Core advertises health-unknown protocol 1; the agent
requires it over pinned local TLS before sending unknown booleans. Legacy or
incompatible transports are refused before heartbeat submission. Existing boolean
health remains readable.

The agent reads actual Windows physical memory with GlobalMemoryStatusEx and
actual target-volume usage. Thermal, interface, IPv6, Bluetooth and peripheral
probes that are not implemented remain unknown/unobserved. No Linux commands or
microphone activation are substituted. The local DE/EN UI displays visible
unknown values and explains that empty peripheral lists are not proof of absent
hardware. Recent authenticated heartbeat still establishes agent reachability;
it does not claim that unknown services are ready.

## Evidence

- Core: 56 gateway/service/authority tests passed, including actual API JSON and
  PostgreSQL round trip retaining null observations; log
  `build/core-unknown-health-tests.txt`. No physical device actions.
- Agent Windows suite: 94 passed, 19 skipped, including actual native RAM/disk
  APIs; subsequently seven new controlled compatibility-fence cases passed.
  The seven cases are HTTP boundary doubles, not actual older-server acceptance.
- Agent isolated Linux suite: 96 passed, 24 Windows-only skips; report
  `build/isolated-linux/gateway-embedded-full-tests.txt`.
- Local Web: three gateway contract tests, changed-file ESLint, complete type
  check and production build passed. Final build log:
  `build/web-unknown-health-build.txt`.
- Actual Chromium + built local Web: eight cases passed across DE/EN, light/dark
  and 390/1440-pixel widths. Unknown metrics and uncertainty text are visible;
  keyboard focus remains reachable and no horizontal page overflow occurs.
  Core/auth are explicit loopback protocol doubles in this browser fixture;
  Core authority is covered separately above. No device actions or external
  browser requests. `build/node-unknown-health-browser-report.json`.
- Modern Web Guidance `accessibility`: preserved visible DOM text rather than
  tooltips, color-only uncertainty or extra live-region announcements. Relevant
  rule: "If content is important, it should be visible for everyone." No widget,
  CSS, focus-order or browser API replacement was introduced. Screen-reader and
  non-Chromium acceptance remain outstanding.

## Remaining scope

Windows prepared-node CLI, scoped task runtime and SCM deployment remain open;
these tested resource and contract components do not constitute Windows node
support. Coordinated task placement/exclusive handoff and node update/backup
integration remain open. Published releases must coordinate the updated Core and
local Web before deploying agents that send null observations. No release was
published and existing private `.15` installers were not rebuilt in this batch.
The full requirement ledger remains binding. Preserve unrelated Web tsconfig
changes.
