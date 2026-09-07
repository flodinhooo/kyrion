# Kyrion public website

Minimal standalone Next.js App Router application for the future kyrion.ch
website. Currently only a static English/German placeholder is implemented.
It has no dependency on Kyrion Core or the local application in `apps/web`.

Run from the repository root with Node.js 20.9 or newer and pnpm 10.29.3:

```sh
pnpm install --frozen-lockfile
pnpm --filter website dev
```

Open http://localhost:3001. Port 3001 keeps the website separate from the local
Kyrion Web application's default port 3000.

Validation and production startup:

```sh
pnpm --filter website lint
pnpm --filter website typecheck
pnpm --filter website build
pnpm --filter website start
```

Next.js generates `next-env.d.ts` during development, type generation and builds.
Dependencies, `.next` output and TypeScript build metadata are ignored by Git.
No formatter or test runner is configured for this minimal scaffold.

The root pnpm workspace currently includes only `apps/website`. The pre-existing
`apps/web` workspace and lockfile remain independent and unchanged; continue
running its pnpm commands from that directory.
