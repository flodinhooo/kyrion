# Existing TTS samples: hearing review and anomaly investigation

Continuation from master `a842b9e`. No new synthesis, benchmark, speed tuning,
engine/voice change or active-stack restart was performed. Existing Chatterbox,
F reference, model choice, guarded V39 Core `2488c1b` and schema39 are preserved.
Calendar/other worktrees were not modified. No migration, cloud request, upload,
download or external service was used.

## Findings and limits

All24 original WAVs match their benchmark SHA256s and declared PCM durations.
The [committed audit](2026-10-31-tts-sample-audit.json) maps every file to input,
input hash, engine/configuration, iteration/seed, synthesis time, audio format,
audio hash, signal analysis and local STT. The original files remain untouched.
Run0 means first use (only MOSS short0 was process-cold), runs1–3 mean warm.

All24 files were transcribed sequentially through the existing local Parakeet
TDT0.6b-v3 q8_0 CPU endpoint at127.0.0.1:8040. No expected-text prompt was supplied.
Transcripts are synthetic diagnostic evidence, **not human acceptance**; even
Chatterbox list transcripts contain occasional word/number errors. The static
pack retains the transcripts under the reveal, away from the initial blind pair.

| Existing MOSS file | Recorded generation | Signal evidence | Local STT indication |
|---|---|---|---|
| `two-3.wav`,20.48s, seed82003 | 256 frames, one text chunk, below375 cap | 16.90s below−40dBFS window RMS; longest contiguous quiet span9.52s; leading0.04s/trailing0.06s | `Ein See ist entstehendes Gewässer. Sein sportiert Wasser durch die Landschaft.` |
| `list-2.wav`,2.80s, seed82002 | 35 frames, one text chunk, below375 cap | 0.64s below threshold; longest0.22s; leading/trailing0.04s | `Dreh den Wasserfahren beim Zähneputzen ab.` No second/third item recognized. |
| `list-1.wav`,6.80s, seed82001; fixed A/B selection | 85 frames, below375 cap | 1.86s below threshold; longest0.80s | First two items recognized; third item absent from transcript. Retained rather than replaced by a better sample. |

Energy analysis uses20ms windows across both channels, without stereo averaging,
at−40dBFS RMS. Quiet energy includes unvoiced/soft speech; it is not certified
silence or VAD. The long output is largely explained by low-energy material,
rather than additional recognized content. No exact repeated nonquiet20ms PCM
blocks were detected in any file. That excludes neither approximate waveform
repetition nor semantic repetition. STT did not identify a repeated sentence in
the long outlier, but only listening can assess its actual intelligibility.

The35 and256 generated frames correspond exactly to the2.80/20.48s PCM durations
(80ms/frame); there is no evidence of a WAV writer or transport clipping a longer
recorded output. Structural completeness does **not** establish spoken completeness.
The short list is consistent with premature model termination, not a hard limit.

The installed MOSS source was inspected, without loading any inference sessions:
`ort_cpu_runtime.py:generate_audio_frames` loops up to `max_new_frames`; the
selected fixed-sampling branch stops when its graph returns `should_continue=false`.
Other branches similarly stop when the assistant token is no longer an audio
slot. Sampling draws seeded random values; `fixed` is not greedy/deterministic
across different seeds. There is no complete-input-coverage check before stopping.
The original benchmark saved counts, not the terminal graph output or token
trace, so the exact termination token cannot be retrospectively proven.

Pure text preparation/tokenization was replayed with the same installed revision,
offline networking disabled and **no model constructor/synthesis call**. Inputs
use16/34/58 text tokens, below the75-token chunk budget; all remain one chunk.
Both sentences and all three list contents survive preparation. List markup
normalization changes142→131 characters, removes numeric prefixes/newlines and
joins punctuation without spaces (`ab.Nutze...beladen.Sammle...`). The existing
normalizer selects its English path for Latin German text. These defaults deserve
awareness, but no changed content or hard text truncation explains the missing
second/third items: other runs with the identical preparation include them in STT.
The replay result and generation defaults are included in the audit, explicitly
labeled as reconstruction rather than the original inference trace.

Therefore no specific correctable configuration/implementation defect was proven.
**No synthesis parameter was changed and no affected sample was regenerated.**
Long low-energy output and likely content omission are investigated; the internal
model cause and human perception remain unresolved. Faster timings must not be
accepted as equivalent complete speech. Stop here for human review.

## Open the local A/B pack

From repository-root PowerShell, the existing generated pack needs only:

```powershell
python -m http.server 8765 --bind 127.0.0.1 --directory .run/dev-recovery/tts-isolated/review
```

Open **http://127.0.0.1:8765/**. Ctrl+C stops only this static review server.
It serves only the prepared directory on loopback, not the repository, Core,
credentials or a public/LAN endpoint. No engine is invoked by the page.
If the port is occupied, use another unused local port in both command and URL.

The pack was generated with the existing Python runtime:

```powershell
python infrastructure/dev/Prepare-TtsListening.py --transcribe
```

That flag only runs local STT on existing synthetic WAVs, cached by content hash.
Rebuild presentation without new STT using the same command **without**
`--transcribe`; `--language en` provides the English version. If ignored local
audio files are lost, the committed audit preserves findings but cannot recreate
the audio; do not silently synthesize replacements for this comparison.

Selection was declared before analysis: **iteration1, first warm run of each
engine for every text**, without speed/quality sorting. Short and list pairs use
the same ordering; two-sentence ordering is reversed for counterbalancing.
The exact per-text mapping is documented in `audit.json` and the closed reveal
section. This is presentation blinding, not protection against inspecting source;
native players display duration. Do not inspect the manifest before rating.

Each pair shows the identical expected German input and ratings1–5 for
completeness, intelligibility, naturalness and suitable voice. Choose A/B/both/
neither and note missing words or endings. Only one player runs at a time. Ratings
are not uploaded or automatically persisted: export the local JSON before reload.
After initial ratings, open the reveal for engine/time mappings and all24 original
runs, particularly `moss-two-3`, `moss-list-2` and the selected `moss-list-1`.
No synthesis time is a full Pi-dialog or acoustic latency.

Decision required after listening: are all intended contents actually spoken,
is the voice suitable, and are the anomalies acceptable? If contents are missing
or long unintended pauses are confirmed, reject MOSS **in this tested configuration**.
A preferred isolated timbre alone does not justify production promotion; active
Chatterbox remains the fallback pending a separate deliberate decision.

## Immediate on-site test and real manual stop

Read-only prerequisites, tested in this continuation:

```powershell
node infrastructure/dev-stack.mjs status
& infrastructure/dev/Probe-PiCore.ps1
& infrastructure/dev/Invoke-VeloraProbe.ps1 -Mode session -InstalledClient
```

1. With the normal Satellite active, say **Hey Velora**, then `Warum ist der
   Himmel blau? Antworte kurz.` Hear the complete answer, volume and word endings.
   Let inactivity end the session.
2. Say **Hey Velora** again, then `Nenne drei Möglichkeiten, Wasser zu sparen.`
   Check all three points, end pieces, section gaps, overlap and stale replay.
   Record actual heard timing on one local clock, preferably phone video from
   end of spoken question to first substantive heard answer; note resolution.
3. **Spoken interruption is missing.** Source still captures before synchronous
   `client.turn`/blocking playback; it does not listen concurrently. Saying
   `Stopp` during playback is not an implemented cancellation control or a passed
   test. No barge-in code was added.

Available operator cancellation test (manually invoked, deterministic termination
~300ms after first answer-player spawn):

```powershell
& infrastructure/dev/Invoke-VeloraProbe.ps1 -Mode manual -Play -InstalledClient -AbortDuringPlayback
```

The probe temporarily stops the Satellite unit, plays the greeting, prints
`READY_FOR_GERMAN_SPEECH`, captures the operator's short question and terminates
the first answer player. It closes the session and restores the previous active
unit in `finally`; the deliberate abort reports failure/nonzero status. It is an
operator cancellation probe, **not** a successful spoken interruption. This
continuation inspected its code/arguments but did not run a new physical dialogue.

For an immediate operator stop of the **normal** unit, use a Pi SSH terminal:

```sh
systemctl --user stop kyrion-voice-satellite.service
# Wake/capture remains stopped until explicitly restored:
systemctl --user start kyrion-voice-satellite.service
systemctl --user is-active kyrion-voice-satellite.service
```

The actual unit was read-only verified as active, `KillMode=control-group`,
`SendSIGKILL=yes`, stop timeout90s; stopping targets its playback children too.
This is service-level stopping, not a clean Core-session close guarantee or
spoken barge-in. It was not executed here. The controlled probe is preferable
when verifying session cleanup. No foreign service or host restart is needed.

## Validation and unchanged operation

Five targeted Python tests passed: signal/identity/truncated-PCM checks,
fixed selection and escaped content, identical-input/path rejection,
content-hash STT cache, matching DE/EN resource keys. Ruff lint/format, Python
compilation and JavaScript syntax passed. Headless Chromium checked three blind
pairs, six decodable A/B audios, reveal, mutually exclusive playback, ratings JSON
export and all24 served WAV hashes; no page errors. Playback was muted: this is
software verification, not acoustic acceptance. One cache test exposed duplicate
hashes allowing an unrated entry to overwrite a transcript; the new preparation
tool now caches only successfully transcribed entries. No engine code changed.

Seven services ready, Pi DNS/TCP/health/401 and installed authenticated
session/greeting/closure checks passed. Read-only Flyway check:39 migrations,
no mismatches or pending versions. Guarded Core hash unchanged:
`50A8174C1931EB7D4614AF8FF580B769831C992FC8CB6526FA3DFF54291DAE23`.
No Core/AI/Satellite build is needed for static tooling/documentation changes.
V39 branch stays `2488c1b`; there is no shared runtime fix to port.

Human ratings and the two actual spoken/acoustic dialogues remain open. Gateway
privileged diagnosis and host startup proof remain separate operational items;
cloud spending and V40 rollout remain unopened. No further automatic TTS round
is scheduled as a substitute for the listening decision.
