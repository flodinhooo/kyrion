# Modern Web Guidance: initial integration and proposal-only audit

Date: 2026-11-13. Scope: local Web and public Website source. No application code,
CSS, provider configuration, runtime dependency or deployed behavior was changed.
This report proposes work; it does not mark the proposals implemented or accepted.

## Integration and reproducibility

The shared project-local upstream skill is pinned to
`GoogleChrome/modern-web-guidance@4dd968349e54ca45a05dd5c818fb035c9054b022`.
Its unmodified guides, SKILL.md, Apache-2.0 license and provenance are under
`.agents/skills/modern-web-guidance`. Both app AGENTS.md files and the root rules
reference [the shared policy](../modern-web-guidance.md). CLI 1.0.0 is invoked only
as a development tool, with telemetry disabled and no application dependency.

Commands: `pnpm mwg:scan:web` and `pnpm mwg:scan:website`.
The initial JSON results are preserved in `2026-11-13-mwg-scans/` beside this report.

| Source             | Static findings | Active rules | Active guides |
| ------------------ | --------------: | -----------: | ------------: |
| `apps/web/src`     |               0 |           35 |            33 |
| `apps/website/src` |               0 |           35 |            33 |

The scanner describes its coverage as roughly 20% of the guidance corpus. Default
test/documentation exclusions were retained (72 excluded local-Web test files).
Zero findings means no match to these rules, not absence of bugs, accessibility
certification, full dependency review or proof of real-browser performance.

Manual review retrieved the `dialog`, `forms`, `efficient-background-processing`
and `accessibility` guides. The suggestions below are source-backed manual findings,
not scanner detections. Runtime impact estimates still need focused verification.
Effort estimates include a narrow fix and relevant regression coverage, excluding
deployment/provider acceptance.

## Prioritized proposals

### MWG-01: Recover device controls after transport failure

- **Surface / priority:** local Web, high. Estimated effort: small (1–2 hours).
- **Evidence:** `apps/web/src/components/device-control-dialog.tsx`, `command()`:
  `setPending(true)` precedes `await fetch(...)`, while resetting pending is at the
  end without `try/catch/finally`. A rejected request bypasses that reset. The
  displayed error paragraph also has no live-region role.
- **User impact:** a network failure can leave the mounted dialog's action buttons
  disabled without useful feedback; assistive technology may miss the failure.
- **Proposed change:** bounded transport handling, guaranteed pending reset, an
  appropriate localized announced failure and explicit user-driven recovery.
  Do not automatically retry a device write: a failed response does not prove the
  device did not execute it. Core checks and confirmations remain authoritative.
- **Verify:** simulate a rejected request and timeout using a mocked integration;
  buttons recover, the error is announced and no extra command is sent. No physical
  household device needs to be switched for this test.
- **Guide basis:** `forms` (AJAX feedback) and `accessibility` (dynamic errors).

### MWG-02: Prevent overlapping installation-directory reads

- **Surface / priority:** Website, medium. Estimated effort: small (1–2 hours).
- **Evidence:** `apps/website/src/components/linked-installations.tsx`, `load()`:
  an interval starts every 5 seconds, requests have a 15-second timeout, and focus
  can trigger another load. There is no in-flight guard or response ordering.
  Cleanup ignores late results but does not abort outstanding transport.
- **User impact:** slow connections can produce concurrent requests and a late
  older result can replace a newer directory snapshot. This is a presentation
  race, not evidence of an authorization bypass.
- **Proposed change:** one active read, abort on cleanup, explicit response ordering
  or a completion-based timer, and bounded retry/backoff. Preserve existing hidden-tab
  suppression, session scoping and manual/focus refresh. Do not pause authoritative
  account/session validation or local safety functions.
- **Verify:** delayed out-of-order responses, repeated focus events, hidden tabs,
  unmount and session change. Confirm one outstanding read and current data wins.
- **Guide basis:** `efficient-background-processing`; its rendering-specific CSS
  technique is not appropriate here. Apply the resource-lifetime principle to the
  existing document-visibility behavior, not blanket offscreen CSS.

### MWG-03: Clear resolved contact-field errors during correction

- **Surface / priority:** Website, medium. Estimated effort: small (1–2 hours).
- **Evidence:** `apps/website/src/components/contact-form.tsx`, `fieldProps()` and
  the submit flow. Text controls receive `aria-invalid` and an associated error,
  but have no correction handler that clears a resolved field error. Errors are
  replaced on the next submission.
- **User impact:** an edited, now-valid value can remain visually and programmatically
  invalid until the user submits again.
- **Proposed change:** clear that field's stale error once its current value passes
  the existing rule; do not announce new errors on each keystroke. Retain first-error
  focus, DE/EN messages, successful server validation, honeypot and delivery semantics.
- **Verify:** submit invalid input, correct it, then check the field message and
  `aria-invalid`; untouched fields stay quiet and invalid values stay rejected.
- **Guide basis:** `forms`, Constraints and Validation / event timing.

### MWG-04: Explore native popover for the account dropdown

- **Surface / priority:** Website, low / optional. Estimated effort: medium
  (2–4 hours including compatibility checks).
- **Evidence:** `apps/website/src/components/account-menu.tsx` uses `<details>`
  plus a document pointer listener, Escape handling, blur handling and focus return.
- **Potential benefit:** native popover may remove part of the manual dismissal
  and top-layer positioning logic. This is not a confirmed defect in the menu.
- **Decision:** defer replacement. The retrieved guide classifies Popover as Newly
  available, outside the conservative Widely available target. Required fallback
  behavior can eliminate the code-size benefit. Keep the current working disclosure
  until a prototype proves a worthwhile gain across the supported browsers.
- **Verify if pursued:** keyboard, Escape/focus return, click outside, mobile clipping,
  Safari/iOS and fallback behavior. Menu navigation semantics must remain navigation.
- **Guide basis:** `dialog`, overlay Rule 3 and Popover fallbacks.

## Keep as implemented

- Radix dialogs (`apps/web/src/components/ui/confirm-dialog.tsx` and device dialogs):
  no wholesale native-dialog rewrite. They already use a coherent modal primitive
  with title/description and explicit action buttons. Tests must still verify focus
  and pending-state dismissal, but no demonstrated benefit justifies replacement.
- Existing native `<details>` management disclosures, labelled controls and server
  validation are useful foundations, not legacy findings.
- The contact form already focuses its first invalid field and connects error text
  with `aria-describedby`. Improve the identified gap rather than replace the form.
- No blanket content-visibility, animation, passkey, polyfill or dependency change.
  Measure long-list rendering before proposing performance work.

## Verification and limits

Both root scan commands and generic search/retrieve execute successfully. The runner
passes Node syntax checking, rejects installation/update commands, and pins the CLI
version with telemetry disabled. Upstream provenance/license and unchanged SKILL.md
checksum were verified. `git diff --check` covers authored integration files.
No application tests/build were rerun because application source and dependencies
were not changed. This audit includes source inspection, not a fresh multi-browser,
screen-reader, Lighthouse or physical-device acceptance run.

Suggested order if authorized: MWG-01, MWG-02, MWG-03. Keep MWG-04 deferred.
