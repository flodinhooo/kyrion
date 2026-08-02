# Kyrion Agent Guidelines

These instructions apply to the entire repository. More specific `AGENTS.md`
files may add rules for their directory but must not weaken the architectural,
security or quality requirements defined here.

## Read before changing code

Before implementing a feature or making an architectural decision:

1. Read `README.md` and the relevant documents in `docs/`.
2. Read every `AGENTS.md` that applies to the files being changed.
3. Inspect the current implementation and configuration; documentation may
   describe intended components that do not exist yet.
4. Preserve unrelated user changes and keep the scope of a change focused.

The project documentation is the source of truth for product direction. If the
implementation and documentation conflict, identify the conflict explicitly
instead of silently choosing one.

## Product foundations

Kyrion is a local-first, modular and auditable platform. Preserve these
principles:

- essential functionality remains usable without AI;
- local processing and storage are preferred whenever practical;
- external providers are optional and transparent;
- user-facing functionality is available in German and English;
- useful vertical slices take priority over speculative infrastructure;
- new complexity must solve a concrete current requirement;
- sensitive or destructive actions are visible and require confirmation where
  appropriate.

## Architectural boundaries

The intended primary components are:

- `apps/web`: Next.js, React and TypeScript web interface;
- `apps/mobile`: React Native, Expo and TypeScript mobile interface;
- `services/core`: Kotlin and Spring Boot authoritative backend;
- `services/ai`: Python and FastAPI AI capabilities;
- `packages/api-contracts`: shared or generated API contracts;
- `infrastructure`: deployment and operational configuration.

Respect the following ownership rules:

- User interfaces present state and collect intent. They must not contain
  provider-specific business rules or expose secrets to the browser.
- Kyrion Core owns authentication, authorisation, permissions, business rules,
  command validation, execution policy, persistence and audit logging.
- The AI service interprets language, retrieves knowledge and proposes typed
  tool calls. It must not directly control devices, access external accounts or
  execute unrestricted operating-system commands.
- Integrations translate stable Kyrion capabilities into provider-specific APIs.
  UI and AI code must not depend on manufacturer-specific details.
- Every AI-proposed action passes through Core validation, permission checks and
  logging before execution.
- Home Assistant is an integration, not the platform core.
- Ollama is a replaceable model runtime, not the system's architecture or sole
  source of intelligence.

Use HTTP and JSON with typed request and response models initially. Introduce
OpenAPI, events, queues, WebSockets or additional services only when a concrete
use case justifies them.

## Plugins and knowledge

Follow `docs/marketplace-enterprise.md` for the long-term extension model.

- Plugins extend integrations or features through versioned contracts and must
  not bypass Core.
- Knowledge packages provide curated knowledge, retrieval material and tool
  descriptions; they are not executable authority.
- Shared knowledge packages, personal knowledge and executable plugin code must
  remain separate.
- Do not prematurely build a public marketplace. First prove contracts,
  permissions, isolation, signing, updates and rollback with official plugins.

## Code quality

- Prefer small, cohesive modules with explicit responsibilities.
- Use strict types at component and service boundaries; avoid untyped payloads
  and unchecked casts.
- Validate all untrusted input at the boundary where it enters the system.
- Keep domain logic independent from frameworks and provider clients where
  practical.
- Use stable machine-readable error codes across service boundaries. Translate
  errors in the user interface.
- Do not hardcode user-facing text in UI components. Use locale resources with
  English as fallback and provide German and English translations together.
- Never commit secrets, tokens, credentials or private user data. Provide
  `.env.example` entries with placeholder values when configuration is needed.
- Do not log secrets or unnecessary personal data.
- Add or update proportionate tests for changed behaviour, especially business
  rules, permissions, integrations and data transformations.
- Run the relevant formatter, linter, type checker, tests and build before
  declaring implementation work complete. Report anything that could not run.
- Do not add a dependency when a small, maintainable implementation using the
  existing stack is sufficient. Explain consequential new dependencies.
- Avoid broad refactors during focused feature work unless they are necessary
  for correctness.

## Security and auditability

- Treat browser input, model output, plugin output and provider responses as
  untrusted.
- Apply least privilege to users, integrations, plugins and service credentials.
- Keep credentials server-side and store only protected credential metadata in
  ordinary persistence.
- Require explicit policy for destructive, costly, privacy-sensitive or
  safety-relevant actions.
- Record who or what proposed, approved and executed important actions, along
  with the result and a correlation identifier.
- Do not expose local device-control endpoints directly to the public internet.
- Medical, care, legal and other regulated features require dedicated review,
  compliance work and appropriate certification; generic platform capability is
  not sufficient.

## Documentation and decisions

- Keep documentation in English, matching the existing technical-language
  policy. User-facing communication may be German or English.
- Update relevant documentation when behaviour, component ownership, public
  contracts or roadmap scope changes.
- Record consequential and difficult-to-reverse architecture choices as an
  Architecture Decision Record before implementation.
- Mark planned architecture clearly; do not document scaffolding as completed
  functionality.
- Keep roadmap items outcome-oriented and avoid fixed deadlines unless the user
  explicitly requests them.

## Delivery expectations

For implementation tasks, finish the smallest complete vertical slice that
delivers user value. Summarise:

- the resulting behaviour;
- important architectural choices;
- files changed;
- verification performed;
- remaining risks or intentional follow-up work.

Do not claim completion based only on generated code. Completion requires
appropriate verification and consistency with Kyrion's documented boundaries.
