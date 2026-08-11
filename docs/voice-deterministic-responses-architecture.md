# Deterministic and templated voice responses

## Status

Accepted architecture, 2026-08-11. The first provider-neutral vertical slice
is implemented under ADR 0010. Final reviewed fixed-response audio assets remain
follow-up work. The dedicated Short-TTS provider search is closed without an
accepted provider for the MVP.

This work is deliberately separate from the ongoing XTTS v2 short-output and
EOS investigation. It must not modify or replace XTTS termination behaviour.

## Context

XTTS v2 produces strong normal and longer dialogue output, but extremely short
answers may contain invented words or continued fantasy speech. Many short
voice responses are not inherently generative. Greetings, acknowledgements,
session endings, command outcomes and some clarification questions often have
known semantics before speech synthesis begins.

Kyrion should exploit that distinction without introducing a growing set of
controller `if`/`else` statements or coupling dialogue behaviour to one TTS
provider.

## Current architecture

The implemented Raspberry Pi dialogue path is:

```text
Satellite
  -> WAV + locale + session/turn ID
Core VoiceDialogueService
  -> AI /speech/transcribe
  -> explicit session-end recognition
  -> otherwise AI /chat/stream
  -> completed free-form answer text
  -> AI /speech/synthesize
  -> complete WAV in an NDJSON audio.chunk event
Satellite
  -> PipeWire playback
```

The live batch path now resolves authenticated session greetings and
post-transcription acknowledgements as fixed responses, and explicit session
endings as fixed farewells. Ordinary answers remain free-form LLM text passed
to the normal speech service. Command templates are ready, but the current
Voice turn does not execute device commands and therefore has no trusted
command outcome to speak yet.

The speech service receives only text, locale and an optional voice ID. At that
boundary it no longer knows whether the text represents a confirmed command
result, a greeting, a clarification, or an ordinary answer. Classifying by
text length in the speech service would therefore be too late and semantically
unsafe.

The relevant existing ownership rules remain:

- Core owns authenticated sessions, turn identity, conversation context,
  command validation, execution results and audit correlation.
- The AI service provides replaceable language and speech capabilities.
- A success response may only follow a Core-confirmed action result.
- TTS providers remain hidden behind provider-neutral contracts.
- The Satellite captures and plays audio but does not decide business meaning.

The current `DeviceCommandResult` already exposes useful structured facts such
as capability, room, requested/succeeded/failed counts, device outcomes and a
correlation ID. The current Voice controller does not yet orchestrate these
command results.

## Decision location

The response-path decision belongs in Kyrion Core after a trusted dialogue,
policy or command outcome is known and before assistant text is persisted and
audio is requested.

Core should create a typed `VoiceResponsePlan`. The AI speech boundary should
resolve this validated plan to audio. It must not infer response semantics from
the number of words or characters.

Conceptually:

```kotlin
sealed interface VoiceResponsePlan {
    val responseType: String
    val locale: Locale
    val voiceProfileId: String
    val variantKey: String
}

data class FixedResponsePlan(
    override val responseType: String,
    val responseKey: String,
    // common fields omitted
) : VoiceResponsePlan

data class TemplateResponsePlan(
    override val responseType: String,
    val templateKey: String,
    val slots: Map<String, ResponseValue>,
    // common fields omitted
) : VoiceResponsePlan

data class DynamicResponsePlan(
    override val responseType: String,
    val text: String,
    // common fields omitted
) : VoiceResponsePlan
```

Stable response types may include:

```text
session.greeting
session.farewell
dialogue.acknowledged
dialogue.rejected
dialogue.clarification.required
command.succeeded
command.partially_succeeded
command.failed
command.target_unavailable
status.no_change
```

These identifiers are machine contracts. German and English wording belongs in
a versioned response catalog rather than controller code.

## Response category A: fixed responses

Category A contains responses with no variable values, for example:

- a generic greeting or farewell;
- a short acknowledgement or rejection;
- a generic success or failure cue where no state detail is required.

Flow:

```text
Trusted outcome
  -> responseKey=session.farewell
  -> catalog selects locale, voice profile and variant
  -> reviewed pre-rendered PCM/WAV
  -> audio transport
```

Pre-rendered audio is appropriate for this category because it provides:

- no autoregressive TTS inference;
- no short-output hallucination risk;
- negligible generation latency;
- reviewed pronunciation, loudness and prosody;
- independence from the health of the active TTS runtime.

An asset identity should include at least:

```text
responseKey
catalogVersion
locale
voiceProfileId
voiceProfileRevision or checksum
variantId
sampleFormat
sampleRate
```

Example layout:

```text
velora-f/
  de/
    session.farewell/
      neutral-01.pcm
      warm-01.pcm
      concise-01.pcm
      manifest.json
```

The assets are derived from, but do not replace, the immutable provider-neutral
Velora voice profile.

## Response category B: templates with variables

Category B contains controlled text with trusted variable values, for example:

- `The light in the gaming room is on.`
- `Two devices were updated.`
- `Should I turn off the light in the office?`
- `Hello, Florian.`

The plan contains a registered template key and typed slots:

```json
{
  "kind": "template",
  "responseType": "command.succeeded",
  "templateKey": "light.power.changed",
  "slots": {
    "deviceName": {"type": "deviceName", "value": "Desk Lamp"},
    "roomName": {"type": "roomName", "value": "Gamingraum"},
    "state": {"type": "powerState", "value": "on"}
  }
}
```

Requirements:

- Only registered templates and slot types are accepted.
- The LLM cannot supply arbitrary format strings.
- State and command-result slots come from Core-owned trusted data.
- Escaping, length limits, locale formatting and pronunciation hints are
  applied centrally.
- Device and room names remain untrusted data, never instructions.
- The rendered text and response metadata are persisted together.

The efficient resolution order is:

1. Render the validated localized template.
2. Look up the complete rendered text in a content-addressed audio cache.
3. Return cached audio immediately on a hit.
4. Use a short-output-safe TTS provider on a miss.
5. Cache the validated result using the complete synthesis identity.

A suitable cache key is:

```text
SHA-256(
  catalogVersion
  + templateKey
  + canonicalSlots
  + renderedText
  + locale
  + voiceProfileRevision
  + synthesisProfileRevision
  + audioFormat
)
```

Frequently occurring finite combinations, such as known rooms and devices,
may be proactively rendered after configuration changes. This is an
optimization and must not create a combinatorial requirement.

Until XTTS short output is reliable, a category-B cache miss should use the
stable batch fallback or a separately measured deterministic short-TTS
adapter. Text being short is not sufficient reason to route it to XTTS.

Generic concatenation of independently recorded words is not recommended.
Coarticulation, timing and sentence melody generally produce audible seams.
Concatenative output should only be considered for specifically authored and
tested prompt segments.

## Response category C: dynamic responses

Open questions, explanations, longer answers and unrestricted dialogue remain
on the normal path:

```text
LLM text stream
  -> phrase-boundary policy
  -> normal provider-neutral TTS adapter
  -> PCM
```

A free-form answer must not be reclassified as category A merely because the
LLM happened to produce one short sentence. Meaning and provenance, not output
length, determine the response category.

## Scalable routing without central conditionals

Core should use a `VoiceResponsePolicyRegistry` whose resolvers consume typed
outcomes:

```text
SessionLifecycleOutcome
CommandExecutionOutcome
PermissionOutcome
ClarificationOutcome
ConversationalIntentProposal
DynamicDialogueResult
```

Conceptually:

```kotlin
interface VoiceResponseResolver<T : DialogueOutcome> {
    val supportedOutcomeType: KClass<T>
    fun resolve(outcome: T, context: ResponseContext): VoiceResponsePlan?
}
```

Dispatch is by outcome type or stable outcome code. Adding a capability then
adds a cohesive resolver, catalog entries and tests rather than another branch
in one global controller.

Resolution priority is:

```text
1. Core-confirmed system, policy or command outcome
2. deterministically recognised bounded session/dialogue intent
3. validated structured AI proposal
4. dynamic LLM fallback
```

The existing session-end recogniser demonstrates a small deterministic intent
recogniser. It should eventually be represented through the same registry, not
expanded into a universal manually coded language parser.

## Structured LLM output

For conversational cases, the AI service may propose a response mode:

```json
{
  "mode": "catalog",
  "responseType": "dialogue.acknowledged",
  "templateKey": null,
  "slots": {}
}
```

or:

```json
{
  "mode": "dynamic",
  "text": "Madrid became the permanent seat of the royal court in 1561."
}
```

Model output remains untrusted. Core validates:

- whether the response type and template are registered;
- whether that type is allowed for the current outcome;
- whether all required slots are present and allowed;
- whether factual slots agree with Core-owned state;
- whether a success claim follows a confirmed execution result;
- whether the locale is valid.

Invalid proposals fall back to dynamic dialogue or a safe typed error response.

Structured output must not delay known Core outcomes. Command success, policy
denial and similar responses do not need an additional LLM call.

## Natural variation

Variation should be curated and reproducible:

```yaml
dialogue.acknowledged:
  de:
    - id: neutral-01
      text: "Okay."
    - id: neutral-02
      text: "Alles klar."
    - id: warm-01
      text: "Gern."
```

Variant selection can use a stable hash of:

```text
ownerId + sessionId + turnId + responseKey + catalogVersion
```

Core may exclude the most recent variant in the session. This avoids obvious
repetition while retaining reproducibility for tests and audits. Variation
should be limited or disabled for safety-sensitive messages where exact
meaning and severity must remain stable.

## Users, aliases and locales

The current user model does not yet contain a personal display name, preferred
form of address or assistant alias. A future `ResponseContext` should make
these explicit:

```text
ownerId
userProfile or displayName
preferredAddress
assistantAlias
locale
voiceProfileId
satellite and room context
conversationId
turnId
```

Consequences:

- Including a user name or alias changes a response from category A to B.
- An assistant alias may affect template wording but must not define platform
  architecture.
- Shared assets are keyed by voice profile and locale, not by user.
- Personalized rendered-audio caches must remain owner-scoped where required.
- German and English catalog entries are maintained together.
- English fallback must not silently produce mixed-language speech.
- Device, room and person names may later carry optional pronunciation hints
  separately from their visible values.

## Component responsibilities

```text
services/core
  DialogueOutcome
  VoiceResponsePlan
  VoiceResponsePolicyRegistry
  response-catalog metadata
  slot validation and locale rendering
  variant selection
  audit metadata

services/ai
  provider-neutral AudioResolver
  PreRenderedAudioProvider
  RenderedTemplateAudioCache
  NormalTtsProvider
  optional ShortDynamicTtsProvider

voice assets and runtime data
  immutable reviewed category-A assets
  generated category-B cache
  manifests and checksums

services/voice-satellite
  unchanged consumer of Core audio events
```

Core decides what may be said. The speech layer decides how an already
validated response plan becomes audio. The Satellite remains a capture and
playback client.

## End-to-end flow

```text
STT final transcript
        |
        v
Core turn orchestration
        |
        +--> session/command/policy outcome -------+
        |                                          |
        +--> structured AI response proposal ------+--> validate
        |                                          |
        +--> ordinary LLM response ----------------+
                                                   |
                                                   v
                                      VoiceResponsePolicyRegistry
                                                   |
                +------------------+---------------+------------------+
                |                  |                                  |
                v                  v                                  v
        A: Fixed plan       B: Template plan                   C: Dynamic plan
                |                  |                                  |
      reviewed asset       render + cache lookup             normal LLM/TTS
                |                  |
                |          hit ----+---- miss
                |                  |       |
                |                  |  existing NormalTtsFallback
                +------------------+-------+--------------------------+
                                           |
                                           v
                              provider-neutral PCM/WAV events
                                           |
                                           v
                                      Satellite playback
```

## Observability and audit

The following bounded metadata can be recorded without logging response text or
audio:

```text
responseType
responseMode=fixed|template|dynamic
responseKey or templateKey
variantId
catalogVersion
locale
voiceProfileId and revision
audioSource=prerendered|cache|short_tts|normal_tts
cacheHit
resolutionLatencyMs
firstAudioLatencyMs
fallbackReason
turnId and correlationId
```

This permits measurement of latency, cache effectiveness and routing behaviour
without exposing conversation content.

## Recommended first vertical slice

The first implementation should remain deliberately small:

- `session.greeting`;
- `session.farewell`;
- `dialogue.acknowledged`;
- `command.succeeded`;
- `command.failed`;
- dynamic fallback.

It should include German and English, two or three reviewed variants for fixed
responses, pre-rendered category-A assets, category-B command templates, cache
metrics and no change to XTTS EOS behaviour.

Tests should cover registry dispatch, slot validation, locale completeness,
deterministic variant selection, cache invalidation by catalog and voice
revision, rejection of unsupported LLM proposals, and the prohibition against
speaking success before a confirmed Core outcome.

## Rejected approaches

### Route by text length

Length does not establish meaning or trust. A one-sentence factual answer may
be dynamic, while a longer command result may still be safely templated.

### Classify in the TTS adapter

The adapter lacks command and dialogue provenance and would couple product
policy to a speech provider.

### Expand controller conditionals

This mixes recognition, business outcome, localization and wording and becomes
difficult to test or extend.

### Trust an LLM-selected success response

Model output cannot establish that an action completed. Only a Core-confirmed
result may authorize that wording.

### Concatenate arbitrary word recordings

Generic word-level assembly is likely to produce unnatural joins and difficult
prosody. Complete cached utterances are preferred.

## Architectural conclusion

Kyrion should not equate short text with deterministic speech. Core should
produce a typed response plan based on semantic provenance:

- category A resolves to reviewed, versioned audio assets;
- category B resolves registered localized templates with typed slots and a
  complete-utterance audio cache;
- category C retains the normal dynamic LLM and provider-neutral TTS path.

The LLM may propose catalog responses but Core validates them. XTTS remains an
interchangeable audio provider and is neither modified nor used as the semantic
router. Because this introduces a durable Core-to-AI response-plan boundary, a
formal ADR should precede implementation.
