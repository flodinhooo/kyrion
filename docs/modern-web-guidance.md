# Modern Web Guidance integration

Installed 2026-11-13 for `apps/web` and `apps/website`. Application code and
behavior are unchanged by this integration. The initial task is an audit and
proposal, not authorization to implement the proposed refactors.
The owner later authorized MWG-01 through MWG-03; their bounded implementation
and verification are recorded in the audit's implementation follow-up. MWG-04
and broad modernization remain outside that authorization.

## Installation and precedence

One shared upstream skill lives in `.agents/skills/modern-web-guidance`, discoverable
by agents supporting project-local skills. Root and app AGENTS.md also reference it
explicitly. Its upstream commit, skill checksum and license are recorded beside
the skill. The upstream files are retained verbatim, including Apache-2.0 LICENSE.
The skill should become discoverable on the next agent turn; agents can read its
explicit path immediately in the current session.

Use the following commands from the repository root:

```sh
pnpm mwg search "accessible form validation"
pnpm mwg retrieve "forms"
pnpm mwg:scan:web
pnpm mwg:scan:website
```

The small runner pins CLI 1.0.0, disables its telemetry, invokes it without a shell,
and exposes only search, retrieve, list and read-only legacy scanning. First use
needs network/cache access. No application dependency, service, deployment change
or automatic update hook is added. CLI search/retrieve may contact upstream;
queries must be generic capabilities, never private data, credentials or code.
The installed guide snapshot is pinned; live CLI results are separately dated
evidence and are not guaranteed immutable by the CLI version alone. Updates require
an explicit reviewed tooling change. Prefer the root runner over the upstream
skill's unpinned `@latest` command examples.

## Browser and implementation policy

- Default to **Baseline Widely available**, including Safari/iOS and Firefox.
- Newer features need feature detection and a usable existing or lightweight
  fallback. Do not add polyfills or dependencies solely to follow an example.
- Keep local-first processing, Core authorization, typed boundaries, DE/EN resources
  and the installed Next.js documentation authoritative. Do not adopt `any` casts,
  browser-side provider logic or telemetry suggestions from generic examples.
- Assess native controls before new custom JavaScript. Existing Radix components
  are not automatically legacy or defective; replacement needs measurable benefit.
- Scans are candidate discovery only. Read the matching guide, inspect context and
  verify the compatibility/fallback rubric before proposing changes. No zero-score
  target justifies deleting safe behavior.
- Keep proposal-only audits separate from implementation. Once a change is authorized,
  use the normal formatter, types, lint and proportionate tests/build; verify keyboard,
  responsive, both-theme and relevant browser behavior.

## Initial results

See [the first audit](status/2026-11-13-modern-web-guidance-audit.md).
