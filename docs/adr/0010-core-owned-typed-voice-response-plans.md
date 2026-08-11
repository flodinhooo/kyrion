# ADR 0010: Core-owned typed voice response plans

## Status

Accepted for the first deterministic voice-response slice on 2026-08-11.

## Context

XTTS v2 remains useful as an experimental, opt-in candidate for normal and
longer speech. Reproducible Short-output experiments found no sufficiently
reliable completion signal in the installed runtime. EOS bias, terminal text
representations, pause-only and multi-signal guards, per-chunk ASR and private
attention instrumentation do not provide an acceptable dynamic Short-output
path.

Many short responses have trusted semantic provenance before speech synthesis:
session lifecycle events, acknowledgements and confirmed command outcomes. A
TTS adapter sees only text and cannot safely recover that provenance. Routing
by text length would misclassify short factual answers and couple product
policy to a provider.

Core already owns voice sessions, conversation state, command validation,
execution results and audit correlation. The AI service owns replaceable
speech capabilities and validates provider output.

## Decision

Core creates a typed `VoiceResponsePlan` after the authoritative dialogue or
command outcome is known and before speech is requested. Plans have exactly
three semantic categories:

- `FixedResponsePlan` selects a registered, versioned response and variant;
- `TemplateResponsePlan` selects a registered localized template with typed,
  Core-validated slots;
- `DynamicResponsePlan` carries ordinary unrestricted dialogue text.

Core uses a resolver registry dispatched by typed outcome rather than a central
conditional chain. Core renders the user-visible German or English text and
persists that exact text with the conversation. Model proposals remain
untrusted: Core validates response type, allowed source and slots, and only a
Core-confirmed command outcome may produce command-success wording.

The Core-to-AI speech request carries the complete typed plan, catalog and
voice revisions, selected variant, locale, voice profile and rendered text.
The AI service resolves audio without changing the response meaning:

- fixed plans first resolve reviewed manifest-backed audio assets;
- template plans first use a complete-utterance content-addressed cache;
- dynamic plans use the existing normal provider-neutral TTS path;
- unresolved fixed assets and template cache misses use an injected normal TTS
  fallback until a separate Short-TTS candidate passes its own benchmark.

The fallback is an explicit availability bridge, not an assertion that the
missing fixed asset is production-ready. Missing fixed assets are observable
and remain an acceptance blocker. No generated or unreviewed audio is committed
as a fixed production asset.

Cache identities include catalog revision, voice-profile revision, synthesis
revision, locale, rendered text, template and canonical slots. A revision
change therefore invalidates previous entries without destructive cache
migration.

Variant selection is deterministic from owner, session, turn, response key and
catalog revision. Catalogs must be complete for German and English before
startup or tests accept them.

## Initial slice

The first registry contains:

- `session.greeting`;
- `session.farewell`;
- `dialogue.acknowledged`;
- `command.succeeded`;
- `command.failed`;
- dynamic fallback.

Session farewell and dynamic dialogue are integrated into the current Core
Voice turn. Greeting, acknowledgement and command outcomes establish typed
resolvers for the next orchestration slices; they do not add a second command
execution path or infer command success from model text.

## Consequences

- Semantic routing remains provider-neutral and auditable.
- Short text alone never selects fixed or templated speech.
- Reviewed fixed audio can later remove inference latency without changing
  Core dialogue semantics.
- Repeated templated utterances avoid synthesis through a revision-safe cache.
- The first request for a new template value still uses the configured normal
  TTS provider until a separately benchmarked Short-TTS adapter is selected.
- Core and AI gain a versioned contract that must evolve compatibly.
- Final German and English Velora assets remain explicit follow-up work.
- XTTS EOS experiments and runtime internals remain unchanged.

## Rejected alternatives

- Routing by character, word or sentence count.
- Classifying response meaning inside a TTS adapter.
- Expanding controller-specific phrase conditionals.
- Allowing an LLM proposal to establish command state or success.
- Committing automatically generated fixed assets without listening review.
- Selecting a new Short-TTS provider as part of this architecture slice.

