# K-AI accounting review and acceptance procedure

Date: 2026-10-31. See [ADR 0034](adr/0034-durable-ai-usage-finalization.md).
Cloud acceptance and physical Velora acceptance are **open**. The instructions
below prepare those operations; they do not authorize spending, deployment,
network exposure or physical device changes.

## Accounting states and guarantees

| Ledger state | Meaning | Charge / next step |
|---|---|---|
| `pending` | Reserved; invocation fence not crossed | Keep reservation; no automatic expiry/refund |
| `invoked` | Invocation committed before network I/O | May be running or interrupted; keep reservation, never replay |
| `uncertain` | Timeout, disconnect, malformed/missing terminal event, legacy unknown invocation or disputed usage | Keep conservative token floor and any known monetary estimate; investigate |
| `estimated` | Generation completed, but complete usage was not supplied | Keep reservation; later trustworthy terminal usage may reconcile it |
| `reported` | Valid terminal input/output usage accepted | Tokens are reported; money is still an estimate, or unknown |
| `rejected` | Core proved it had not invoked the provider | Zero charge; no later invocation/settlement allowed |

Token confirmation is **not** invoice confirmation. `costBasis` distinguishes
reservation estimates, estimates using provider usage and non-invocation.
Missing prices/currency and unmodelled token categories remain unknown. They
must not disappear into SQL `SUM(NULL)` or a zero monetary charge. A monetary
limit rejects new requests when existing current-period cost is unknown or in a
different currency. Observed partial usage above the reservation increases its
token/cost floor. Actual usage above a budget remains recorded; subsequent
requests are blocked, not retroactively relabelled as free.

Budget checking and initial insertion use one captured UTC month after the
account lock. Later settlement stays in that period and uses the stored price
snapshot. An ordinary new turn belongs to its own month; the previous attempt
remains visible. The actor/request/attempt uniqueness constraint survives
restart/month boundaries. Reusing a prepared generation cannot invoke twice.
Fallback is still generation policy, never a billing-reconciliation mechanism.

Only Core's internal settlement path accepts usage observed through its trusted
server transport. No browser route can submit totals, choose an actor/Space or
refund a reservation. Conditional transitions and correlated audit events share
the transaction; audit failure rolls back the ledger change. Repeated identical
reports are no-ops. Conflicting terminal reports open `USAGE_CONFLICT` once,
preserve the first counters, restore a conservative token floor and mark money
unknown. Later callbacks cannot silently resolve that dispute.

V40 is additive. It conservatively changes old `pending` attempts to `uncertain`
with `LEGACY_REVIEW_REQUIRED`; it does not invent past invocation times/prices.
The active installation is not migrated by building/testing this feature.

## Investigating open cases without paid retries

1. Open Settings → Models → My AI usage. The DE/EN view lists the oldest100 open
   cases across **all months**, including reported tokens whose monetary cost
   remains unknown. A truncation notice means additional cases remain stored;
   nothing is forgiven or removed. `invoked` is not proof a worker is still alive.
2. Record the attempt ID, actor, original month, provider/profile, error and token/
   cost basis in private operator notes. Use the ledger's `request_id` to inspect
   the correlated `ai.usage.reserved/invoked/settled/disputed` activity entries.
   Do not export raw prompts, account secrets or other users' source metadata.
3. Inspect retained server transport evidence and, with appropriate account
   access, read-only provider billing/export information. A matching terminal
   stream observation may re-enter Core's internal `settle` once; it must contain
   bounded, consistent input/output counts and no transport error. Pricing comes
   from the reservation, never a changed profile or caller's current prices.
4. The current adapters have **no durable provider billing-lookup connector** and
   do not persist a provider invoice/request identifier suitable for automatic
   recovery after losing the stream. Dashboard totals alone do not identify an
   attempt. If evidence cannot be attributed, leave it open and conservatively
   charged. Do not rerun generation, edit SQL, delete the ledger or mark it free.
5. A future provider connector/operator resolution workflow needs its own typed
   evidence/attribution contract and authorization/audit review. `USAGE_CONFLICT`
   and unavailable historical prices require that workflow; they are not
   automatically resolved by another completion callback. Keep unresolved cases
   when rotating keys, deleting conversations or crossing UTC month boundaries.

Account/Space permission denial still blocks usage inspection. Finalizing a
previously incurred attempt remains a server accounting operation even if its
interactive session expires; it grants no new inference or source access.

## Cloud acceptance plan — not executed

No spending authorization was found in the session. The running AI catalog
reports OpenAI, Anthropic and Gemini as unconfigured and disabled. Existing
tests simulate their transports. Keys remain server-side; do not print/load
their values for this preparation or put them in model-profile JSON.

Start with **one explicitly approved provider** and an isolated synthetic test
account/project. Proposed first candidate: OpenAI **`gpt-5.6-terra`**, Responses
API. The official model page lists text input/output, streaming and rates of
USD2 input / USD12 output per million tokens. Account access and current pricing
must be rechecked before approval; this is an acceptance candidate, not a model
recommendation. [Official OpenAI model documentation](https://developers.openai.com/api/docs/models/gpt-5.6-terra).

Proposed envelope: **USD0.10 total for this provider's run, at most three real
requests**, one at a time, maximum1024 output tokens, no native tools, caching
writes, search, attachments, memory/history disclosure, parallel calls or
fallback. Configure a fresh account's monthly token ceiling36000, request
reservation ceiling12000 and USD0.10 estimated monthly cost ceiling; verify the
conservative reservation fits before each request. Use available provider-side
spend/quota restrictions separately. Kyrion's estimate is not an exact provider
billing guarantee. A timeout, incomplete usage, refusal, output limit or unknown
cost ends the run; no paid fault injection/retry is authorized by this plan.

Operator preparation after explicit approval:

- Provision the key only in the protected AI-process environment. Enable cloud
  separately in Core/AI. Configure a fixed `acceptance-openai` profile using the
  model/rates above, currencyUSD, capabilities `chat,streaming`, context32768,
  output1024 and bounded connect/read/total timeouts5/60/90 seconds. Do not deploy
  or restart the active stack as part of this document's preparation.
- On the isolated account, allow only that provider/profile, enable cloud in
  policy and personal preferences, disable local-only only for that account,
  keep fallback disabled and require exact provider consent per message. Preserve
  original settings for a deliberate later rollback. No shared context is released.
- Before network calls, repeat the mocked failures: missing consent, local-only,
  denied provider/profile, unknown price/currency, exhausted budgets, 401/429/5xx,
  malformed/truncated stream, disconnect, missing counters, duplicate/late report,
  foreign account/Space and revoked session. Assert no unauthorized provider call.
- Real request1: new synthetic turn, `Reply with exactly OK.`; request2: new turn,
  `Antworte nur mit OK.`; request3 only if needed and still within the approved
  envelope: another short synthetic text response. Use authenticated Web → Core
  → AI, not a direct AI request that bypasses Core policy/accounting.
- Capture the selected provider/model, text deltas, final event, input/output/
  total metadata, attempt/request IDs, original-period ledger and estimated cost.
  Confirm one invocation and one successful settlement per request. Replay the
  same owned turn through Core:409 / no second provider invocation. This replay
  is a refusal check, not an authorized additional paid request.
- Pass only if DE/EN text, normalized stream, consent/privacy exclusions, accurate
  attribution and usage persistence agree, with no unresolved accounting case.
  A missing usage field is a documented failed acceptance case, not zero cost.
  Compare with provider billing when available; retain differences for review.
  Revoke the test key/disable the test profile and restore the isolated account's
  local-only settings after the operator-owned run.

Separate compatibility candidates, each requiring its **own** approval/envelope:

| Provider | Concrete candidate | Reference / acceptance gate |
|---|---|---|
| Anthropic | `claude-haiku-4-5-20251001` | Legacy candidate, USD1/5 per million input/output; verify account availability before proceeding. [Official model page](https://platform.claude.com/docs/en/models/haiku-4-5/overview) |
| Gemini | `gemini-2.5-flash` | Existing-account access is restricted; do not silently substitute another model. Standard text USD0.30/2.50 per million input/output including thinking. Extra categories must remain unknown unless priced. [Model/access](https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash), [pricing](https://ai.google.dev/gemini-api/docs/pricing) |

Use the same USD0.10/three-request maximum and fail-closed Core checks for each
separately approved run. Unavailable/deprecated models require a revised plan
and renewed approval, not an automatic switch. Native tool normalization stays
mocked; the generic generation surface intentionally does not execute tools.

## Practical Raspberry Pi Velora checklist — physical acceptance open

The implemented path is local ONNX wake detection → bounded ALSA/VAD capture →
authenticated satellite/Core session → STT → Core action policy or K-AI routing/
context/accounting → TTS → validated audio → PipeWire/Bluetooth playback → Core
playback acknowledgement. General LLM text is collected before TTS. PCM transport
prototypes do not establish full-duplex voice. Satellite identity is a device,
not a speaker: generation uses `personalContextAllowed=false`; no personal
history, memories, calendar or documents may be spoken for an unknown speaker.
Business Voice remains guarded. Source: satellite runtime/core client and
Core `VoiceDialogueController` / `AiOrchestrationService`.

1. Read `node infrastructure/dev-stack.mjs status`. Require all seven local
   services ready and the intended local model present. Run the existing
   `Probe-PiCore.ps1` read-only network probe with the pinned SSH identity. Core
   currently binds loopback: physical testing is blocked until the separately
   reviewed LAN procedure is deliberately applied. Do not weaken firewall rules,
   change DNS/Pi-hole or reuse the obsolete `Set-CoreLan.ps1 -Apply` instructions.
2. On the Pi, inspect `systemctl --user status kyrion-voice-satellite.service`
   and `journalctl --user -u kyrion-voice-satellite.service --since '10 min ago' -o short-iso`.
   Verify the enrolled satellite/configured microphone and selected PipeWire/
   Bluetooth sink. Never print the credential/config file. The existing session
   and synthetic-stop probes validate network/auth/audio shape only; neither
   opens the microphone nor proves speaker playback. Unit tests for both probes
   are in `services/voice-satellite/tests/test_operator_*_probe.py`.
3. Record20 physical attempts:10 DE and10 EN, covering wake/greeting, a short
   neutral question, follow-up without wake, explicit stop, new wake, and a
   repeated wake during an existing session. Require correct language, audible
   intelligible output and return to wake detection; no repeated action/charge.
   Fail on any personal-context disclosure. Device actions require a separately
   authorized safe target and must obey processing audio → execution → truthful
   outcome order; omit them until that authorization/hardware is available.
4. Use one observer's stopwatch/video for wake→greeting and end-of-speech→first
   audible response. Record cold/warm separately, median and p95, language,
   attempt/session/turn IDs and failures. Proposed warm test gates are greeting
   within3 seconds and first response within15 seconds for a short neutral turn;
   these are acceptance targets, not measured product claims. Require at least
   19/20 successful ordinary trials and zero security/duplicate-action failures.
5. Correlate Core `stt_start/stt_complete`, `llm_request/llm_complete`,
   `tts_request/tts_first_audio/tts_complete`, `satellite_first_chunk_sent` and
   `satellite_playback_completed` events by turn ID. Use timestamp differences
   within the same clock domain. Cross-host one-way timing requires clock sync;
   the physical stopwatch result remains the end-to-end measurement.
6. With a controlled test installation, test AI/STT/TTS unavailable, Core session
   expiry/cancellation and a Bluetooth disconnect/reconnect. Require a clear
   failure/no false success, no autonomous cloud fallback/retry, conservative
   ledger state and recovery on the next wake. Do not stop/restart WSL or live
   shared services merely to inject faults; use mocks until an isolated target
   and operator test window exist.

Diagnose in order: no wake → microphone/ONNX/threshold/VAD; no session → DNS/TCP/
TLS/satellite enrollment and Core bind; bad transcript → capture/STT; no answer
→ Core permissions/router/budget and AI/Ollama; no audio → TTS readiness/WAV
validation; sent but inaudible → PipeWire/Bluetooth sink; repeated operation →
session/turn ID and playback acknowledgement plus Core audit. Keep WSL/Docker
outage evidence separate from product/permission/ledger failures. Do not claim
physical acceptance from green unit tests, health endpoints or a synthetic WAV.
