<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="branding/logo/kyrion-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="branding/logo/kyrion-light.svg">
    <img alt="Kyrion" src="branding/logo/kyrion-light.svg" width="560">
  </picture>
</p>

# Kyrion

A local-first platform connecting devices, household services, information and
optional AI through one controlled foundation. Kyrion is a working development
prototype, not a generally available consumer or business product.

Core validates identity, permissions and actions; AI never receives unrestricted
execution authority. Essential local controls can be used without AI. External
accounts, cloud models and their network requirements are optional and explicit.
The Web interface and public website support German and English.

> **LLM proposes. Core decides. Adapter executes. Result confirms.**

**Website/documentation reviewed 2026-11-12:** website source is integrated on
`master`; [current website acceptance](docs/status/2026-11-12-website-acceptance.md)
separates passing local verification from outstanding production acceptance.
Parallel installer work and older platform evidence retain their own scope.
The [current status](docs/status/README.md) separates implementation, tests,
deployment and physical/provider acceptance. The [active backlog](docs/status/TODO.md)
is the current work order, with stable IDs and completion criteria.

> **Licence:** no repository `LICENSE` has been selected. Kyrion is intended for
> open-source publication, but the current source remains all rights reserved;
> do not assume permission to reuse or redistribute it.

## What the prototype implements

- **People and access:** protected local first-owner setup, password login,
  session revocation, system/custom roles and bounded revocable invitations.
  [Spaces](docs/kyrion-spaces.md) support HOME or BUSINESS configuration with
  **one Space per installation**. Optional mailbox/domain verification and
  host-local owner recovery exist. Multi-Space runtime and Business Voice stay
  guarded; room/device permission scopes remain planned.
- **Optional central identity:** explicit [account linking, central login and
  unlinking](docs/unified-identity.md) preserve local accounts, roles and independent
  local password login. Website login grants no local membership. Real isolated
  identity acceptance exists. Public HTTPS discovery and the enabled website
  account endpoint were rechecked on 2026-11-12; real registration, login,
  verification/reset mail and local linking acceptance remain separate. Cloud
  invitations are not established by website login.
- **Public website:** bilingual informational, Contact, Account, Privacy,
  Download and Hardware pages are integrated. The audited source passes 46
  isolated tests, lint, formatting, TypeScript and production build. Seven old
  generated builds were removed. Canonical-host and factual privacy corrections
  are local source changes awaiting publication; actual contact delivery,
  account journeys, deployed abuse controls and installer downloads remain open.
  See [website status](apps/website/STATUS.md) and KY-020–KY-024 in the backlog.
- **HOME calendar:** local events and jointly editable native household events,
  explicit participants, revision conflicts, creator-only deletion, voluntary
  private/availability/details disclosure and manual selected-recipient Google
  delivery with per-target status/retry. Personal copies are retained on native
  deletion. [Family calendar](docs/home-family-calendar-plan.md) software and
  browser-fixture evidence do not close real family/provider acceptance.
  Recurrence/all-day authoring and automatic family delivery remain planned.
- **Rooms, lighting and integrations:** persistent rooms/catalog/availability,
  Nanoleaf controls, selected Hue/Zigbee and MELK-OA20 Bluetooth commands via an
  authenticated gateway. [Home Assistant](docs/home-assistant-import.md) is a
  selected inventory import with separately consented light/switch power control
  through Core. Source-built synthetic full-stack evidence is recorded in the
  [2026-11-11 continuation](docs/status/2026-11-11-installer-continuation.md);
  full physical acceptance remains open. Direct Shelly code remains experimental.
  Discovery does not grant control. Legacy button bindings
  require explicit human review/resave before grants become effective.
- **Media:** [Lounge](docs/lounge.md) includes Core-owned Spotify OAuth/Connect
  controls and validated YouTube links with a visible browser player. Phone-to-Pi
  Spotify evidence does not certify the Web receiver or invited-account path.
- **AI and personal knowledge:** provider-neutral chat and typed device proposals,
  model profiles/policies/accounting, optional personal memory/context and personal
  PDF/text ingestion/retrieval with sources. Ollama has local generation evidence;
  OpenAI/Anthropic/Gemini adapters have simulated cloud acceptance. Current cloud
  release is limited to the consented current message. Real local RAG, nonempty
  knowledge recovery, parser/scale and lifecycle acceptance remain open; shared
  Business knowledge, OCR and cloud document context are unavailable.
- **Velora:** local `Hey Velora`, VAD/capture, provider-neutral Parakeet STT,
  Core-owned voice sessions and reviewed/cached/dynamic batch speech paths.
  Selected physical voice results exist. Repeatable audio quality, end feedback,
  continuous playback and acoustic latency remain open; under-three-second first
  answers and spoken barge-in are not achieved.
- **Operations:** correlated activity/audit, backup and isolated restore tools,
  bounded development recovery helper, schema-only migration tooling and guarded
  [guided Installer candidate](docs/guided-installer.md) with local target probes,
  signed-image verification, fresh Linux orchestration and existing Core onboarding.
  This is not a released installer, safe general updater or complete disaster
  recovery system. No public signed installable bundle is supplied.

## Current priorities and evidence

The next acceptance gates are authenticated HOME/calendar use, explicit legacy
binding review, optional productive central identity, physical Voice/audio and
full-host/off-host recovery. Website publication, mail, account and privacy/abuse
acceptance are now explicit KY-020–KY-024 gates. Installer clean-room/release
acceptance follows its own gates. Details are in the [backlog](docs/status/TODO.md).

The [2026-11-06 Windows/Pi V46 report](docs/agent-handoffs/2026-11-06-v46-live-rollout.md)
records actual Core/Web activation, original-key restore drills and anonymous
DE/EN production browser checks. It does not prove an authenticated owner/family
journey, provider writes or hardware acceptance. The
[isolated identity scenario](docs/agent-handoffs/2026-11-06-identity-master-integration.md)
used real fixture services, separate from productive identity.
The [original Pi identity pilot](docs/agent-handoffs/2026-11-06-central-identity-pi-pilot.md)
was loopback-only. [Later public transport and central SMTP evidence](docs/agent-handoffs/2026-11-07-central-identity-tunnel.md)
and the [current website recheck](docs/status/2026-11-12-website-acceptance.md)
supersede that blanket deployment description. Central SMTP evidence does not
prove contact-form delivery from Vercel; lifecycle/recovery and real-user
acceptance remain open.
These reports are dated evidence, not current runtime-health guarantees.

## Architecture

```text
Web / Voice Satellite / future Mobile
                  |
                  v
             Kyrion Core
 identity | permissions | policy | persistence | audit
          /                       \
         v                         v
Integration adapters       Optional AI capabilities
Nanoleaf / Gateway / ...   chat / retrieval / STT / TTS
```

Web collects intent and presents results through same-origin routes. Kotlin/Spring
Boot Core owns authorization, domain validation and execution. Python/FastAPI AI
interprets requests and supplies untrusted typed proposals. Gateway and Satellite
perform bounded device/audio work; manufacturer details stay in adapters.
Home Assistant is an integration and Ollama a replaceable runtime.
See [architecture](docs/architecture.md), [principles](docs/principles.md),
[product strategy](docs/product-strategy.md) and [ADRs](docs/adr/).

## Repository layout

```text
apps/web/                 local Next.js/React/TypeScript interface
apps/website/             independent public Next.js website
apps/mobile/              package scaffold; no mobile application yet
services/core/            Kotlin/Spring Boot, PostgreSQL/Flyway, Java 21
services/ai/              Python 3.12+ FastAPI AI and speech boundary
services/gateway-agent/   bounded gateway/device runtime
services/voice-satellite/ local wake, capture and playback runtime
packages/api-contracts/   contract scaffold
infrastructure/           development, identity, node and installer tooling
docs/                     contracts, decisions, evidence and active backlog
branding/                 shared branding assets
```

## Development start

Use Node **22.21.1**, pnpm **10.29.3**, Java **21** and Python **3.12** to match
CI. Core integration tests require Docker for disposable PostgreSQL. Real devices,
provider accounts and large model downloads are not needed for standard checks.

The public website runs independently:

```sh
pnpm install --frozen-lockfile
pnpm --filter website dev
```

Open `http://localhost:3001`. See [website setup](apps/website/README.md) for
lint, formatting, type generation, build and isolated Playwright tests.
The root workspace covers only the website. Web has its own lockfile:

```sh
cd apps/web
pnpm install --frozen-lockfile
pnpm dev
```

Before starting the local platform, follow [development startup](docs/development-startup.md)
for PostgreSQL, protected keys/setup, Core, Web and optional AI/speech services.
Do not point test tools at personal databases. Copy only documented placeholder
configuration and keep credentials, recordings, models and private data out of Git.
The Windows recovery helper is development tooling, not production lifecycle management.

Python components declare development extras in their own `pyproject.toml`:
install `'.[dev]'` in a separate virtual environment, then run `python -m ruff check .`,
`python -m pytest` and `python -m build` (install `build` for packaging).
No Python lockfiles currently exist. For Core, build `bootJar` first and set
`KYRION_MIGRATION_REHEARSAL_JAR` to its absolute path before the full test suite;
CI and the isolated schema runner document the exact commands.
See [maintenance verification](docs/status/2026-11-07-maintenance.md).

## Roadmap and contribution

General automations, wider integrations/Matter/Thread, multi-HOME membership,
mobile/remote access, energy views and signed plugin lifecycle remain separate
future slices. Prove official plugin contracts before a public marketplace.
Business subscriptions, hosted teams and privileged remote support are not offered.
The [roadmap](docs/roadmap.md) describes direction; the active backlog sets priorities.

Read [AGENTS.md](AGENTS.md) before changes. Preserve Core authority, least privilege,
DE/EN parity and the distinction between implemented, tested, deployed, physically
accepted and planned. Public contribution guidance and a licence are still pending.
