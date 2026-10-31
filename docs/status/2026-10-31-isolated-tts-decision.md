# Isolated local TTS decision, 2026-10-31

Later continuation: [prepared blind A/B review and anomaly investigation](2026-10-31-tts-listening-review.md).
Use its loopback start command and `review/index.html`, rather than the original
unblinded listening page. All24 existing WAVs now have local STT/signal/provenance
records; no new synthesis or active-stack change occurred. The20.48s outlier is
mostly low-energy material; STT suggests missing list contents in short runs.

## Decision and preserved runtime

Keep the existing Chatterbox path active. MOSS-TTS-Nano ONNX CPU is a faster
**unaccepted listening candidate**, with substantial output-duration anomalies.
Do not promote it or begin another tuning round before reviewing these samples.
This bounded experiment supersedes no earlier voice-quality rejection or manual
acceptance gate. A valid PCM file does not establish complete spoken content.

Starting master: `6b2b5bc`; active compatibility branch
`fix/core-v39-voice-compat`: `2488c1b`. No production code/configuration, model,
voice, service or launcher was changed/restarted. Calendar and other worktrees
were preserved. Core PID11180 still uses the immutable guarded-start copy of
`voice-boundary/core-runtime.jar`, SHA256
`50A8174C1931EB7D4614AF8FF580B769831C992FC8CB6526FA3DFF54291DAE23`.
The read-only gate found39 installed migrations, no checksum mismatches, no
pending migrations and no active Calendar leases. No V40 migration, cloud call,
deployment, Docker reset, download or host restart occurred. Existing rollback
instructions in [the preceding report](2026-10-31-voice-section-boundary.md)
remain valid; there is no new runtime rollback to perform.

Rechecked unchanged source SHA256s: AI `app.py`
`c7b463aee45d46550202fc3bc4ad2a90e60524d6fa63d09c295b796bf0200d77`,
AI `speech.py`
`60a8412cd840e542a6ee7c55cff5cee19a8bf72b22611dc2cbe3069fa46a2cdb`,
Chatterbox server
`fc80f752e652bad5c43be979f2b689f7d4c5f2124a905e2096abea8bcd7f24f7`.
Installed Satellite0.1.0 resolves `core_client.py` under
`/home/flodinho/.local/share/kyrion/voice-satellite/src/src/kyrion_voice_satellite/`,
hash `3d8c527ffac0febcf4bd45321e1362d3f56f2913251700ee41ecdc5695febadd`.

## Actual installation and selection

- Chatterbox-TTS0.1.7, Torch2.6.0+cu124/CUDA12.4, multilingual
  `ChatterboxMultilingualTTS.generate`, RTX2070/8192MiB. The selected T3 checkpoint
  contains292 F32 tensors; source loads default precision and has no half/autocast
  override. This is checkpoint/source evidence, not live tensor inspection.
  Resident Linux PID1330 loads the model/reference once, prepares exaggeration
  0.45, generates German with CFG0.5, temperature0.65, repetition penalty2.0.
  Installed multilingual, standard and Turbo classes expose batch `generate`,
  without a supported audio-stream method. A different class/model would not be
  an unchanged-voice optimization. Prior T3/decoder measurements remain applicable.
- Current F reference SHA256:
  `D2AFDC5FAA3FB6CC41756DAAAAC3DB63C30679E3BCD3E87F6DAB0055D08DAD09`.
  Same reference supplied to the candidate; this does **not** establish voice
  identity. Chatterbox reference conditionals are already cached; candidate uses
  its existing public reference-processing API, without adding cache internals.
- Existing XTTS0.22.0, Qwen-TTS0.1.1 and CosyVoice installations/models were
  inspected alongside prior reports: unstable XTTS termination hooks, Qwen
  Turing FP16/FP32 limits and CosyVoice's prior nearly-batch delivery give no
  stronger bounded candidate. Piper's earlier voice rejection remains relevant.
- Exactly one alternative tested: local MOSS-TTS-Nano100M ONNX, checkout
  `cc7bdf19c7639c0870dab22045a33b442760f6be`, ONNX Runtime1.28.0, Torch2.7.0,
  CPUExecutionProvider, two threads, `nice10`, fixed-sampling seeds82000–82003,
  max375 frames/chunk, existing normalization enabled. Existing model/codec assets
  only; no conversion, precision override or quantization experiment. Audio arrays
  are float32; graph-weight precision was not independently audited. The installed
  README lists German among20 supported languages; this is capability documentation,
  not measured German quality or voice likeness.

The candidate's public `synthesize(streaming=True)` internally decodes chunks but
concatenates and writes the entire WAV before returning. It provides no playable
chunk callback: this is **batch delivery**, not measured streaming TTFA.
See the [official source at the installed revision](https://github.com/OpenMOSS/MOSS-TTS-Nano/blob/cc7bdf19c7639c0870dab22045a33b442760f6be/onnx_tts_runtime.py).
Chunk size, playout buffer and underruns are therefore not applicable to this
experiment; no private streaming hook or new provider/API was built.

## Method and measurements

`infrastructure/dev/Benchmark-IsolatedTts.py` executes engines sequentially,
using WSL `CLOCK_MONOTONIC`, one first-use request plus three warm requests per
text. Timing starts before HTTP/public synth invocation and ends after a complete
PCM WAV is written and validated. **First playable = total synthesis/delivery
time** under these exposed batch APIs; this conservative boundary includes file
validation. It excludes model loading, STT, LLM, Core, Pi transport and playback.
These numbers are not full-dialog or acoustic latency. RTF is elapsed/audio
duration, not CPU utilization or CPU-seconds. Reference HTTP overhead is included.

Identical UTF-8 input strings (45/88/142 characters):

1. `Die Luft streut blaues Licht besonders stark.`
2. `Ein See ist ein stehendes Gewässer. Ein Fluss transportiert Wasser durch die Landschaft.`
3. `1. Drehe den Wasserhahn beim Zähneputzen ab.` followed by newline,
   `2. Nutze Waschmaschine und Geschirrspüler nur voll beladen.` then newline,
   `3. Sammle Regenwasser für den Garten.`

MOSS normalization reports142→131 characters for the list. Inputs are identical,
but internal normalization/output semantics need listening review; speed ratios
must not be read as quality-equivalent improvements. No run hit the frame cap.

| Text | Chatterbox warm seconds, median [range] | MOSS warm seconds, median [range] | Median RTF, Chatterbox / MOSS |
|---|---|---|---|
| Short | 4.852 [4.186–5.235] | 3.062 [2.863–3.350] | 1.349 / 0.994 |
| Two sentences | 6.995 [6.464–7.155] | 3.682 [3.641–10.001] | 1.315 / 0.667 |
| Three list items | 13.027 [12.632–14.338] | 4.187 [2.703–5.199] | 1.215 / 0.616 |

Raw run pairs below are **elapsed seconds / audio seconds**. Index0 is separate
from warm statistics; all three warm outputs are retained, including anomalies.

| Engine / text | First use, index0 | Warm1 | Warm2 | Warm3 |
|---|---|---|---|---|
| Chatterbox short | 4.268 / 3.44 | 4.186 / 3.52 | 5.235 / 3.88 | 4.852 / 3.40 |
| Chatterbox two | 7.333 / 5.40 | 7.155 / 5.44 | 6.464 / 4.84 | 6.995 / 5.40 |
| Chatterbox list | 13.738 / 10.92 | 14.338 / 11.16 | 12.632 / 10.92 | 13.027 / 10.72 |
| MOSS short | 9.293 / 2.80 | 3.350 / 3.20 | 3.062 / 3.52 | 2.863 / 2.88 |
| MOSS two | 3.803 / 5.52 | 3.682 / 5.52 | 3.641 / 5.44 | 10.001 / 20.48 |
| MOSS list | 5.371 / 9.20 | 4.187 / 6.80 | 2.703 / 2.80 | 5.199 / 8.88 |

Candidate process-cold load/import:28.705s, followed by first synthesis9.293s
(37.998s combined, excluding preliminary inventory/GPU query). Texts2/3 index0
are first-use-text, not model-cold. Chatterbox remained resident deliberately:
**a true Chatterbox cold restart comparison was not performed** to preserve the
active fallback. Its index0 is not labeled cold. Both sets used the same machine,
texts and reference, but different engines/hardware and stochastic outputs;
claims of equal pronunciation/content are explicitly withheld.

CPU: AMD Ryzen7 5700X3D,8 cores/16 logical processors, also identified inside WSL;
candidate inference was limited to two threads. Resource checks: WSL
initially~26.8GiB available RAM; Windows~34.5GiB free RAM,
physical E drive~1.38TB free. GPU initially7434/8192MiB used, insufficient headroom
for another GPU engine. During benchmarks GPU before/after snapshots were
6977/6979MiB (Chatterbox) and6962/6962MiB (MOSS); these are not peak measurements.
Peak100ms-sampled resident RSS: Chatterbox2.852GiB, MOSS3.646GiB;
MOSS process high-water RSS3.652GiB. Chatterbox request queue headers were0ms
throughout. Candidate process exits after completion, freeing its memory.
MOSS network connection/DNS methods were disabled before runtime import; offline
flags and an8GiB available-memory gate apply before loading and every request.
Existing normalizer caches were reused. An ONNX device-discovery warning did not
change the selected CPU provider. No OOM, service loss or GPU-memory increase was
observed during the candidate; health checks cannot exclude smaller contention.

Local evidence (ignored, synthetic content only):
`.run/dev-recovery/tts-isolated/{chatterbox,moss}/results.json`, per-run WAVs and
`listening.html` with all18 warm samples. Each JSON row contains sample format,
WAV SHA256, timing, audio duration, RTF, RSS and engine/frame metadata. The MOSS
20.48s two-sentence output and2.80s full-list output must be heard in particular:
structural WAV validation cannot establish whether they repeat, omit or distort
words. No sub-three-second dialogue or accepted voice claim is made.

Reproduce only in a quiet local window, sequentially (replace PID after checking
the actual resident process; do not restart it just for this comparison):

```powershell
wsl.exe -d Kyrion-Voice-Training -- /usr/bin/timeout 600s /usr/bin/nice -n 10 /training/moss-tts-nano-venv/bin/python /mnt/e/dev/Kyrion/kyrion/infrastructure/dev/Benchmark-IsolatedTts.py --engine chatterbox-http --server-pid 1330 --output /mnt/e/dev/Kyrion/kyrion/.run/dev-recovery/tts-isolated/chatterbox
wsl.exe -d Kyrion-Voice-Training -- /usr/bin/timeout 600s /usr/bin/nice -n 10 /training/moss-tts-nano-venv/bin/python /mnt/e/dev/Kyrion/kyrion/infrastructure/dev/Benchmark-IsolatedTts.py --engine moss-cpu --output /mnt/e/dev/Kyrion/kyrion/.run/dev-recovery/tts-isolated/moss
```

## Section pause: no speculative runtime change

Re-examined the prior recovery trace using the unchanged active artifact:
`.run/dev-recovery/voice-boundary/recovered-q1.jsonl`, turn
`7b45d2c0-e7b3-4cdc-9e04-8a786d388a05`. All following differences use the
respective process's monotonic timeline; no cross-host clock subtraction.

- Core section0 ready13380ms, flushed13402ms; section1 synth starts13406ms:
  only4ms after flush. The next section is already prepared during Pi playback.
- Core section1 ready21090ms:7684ms after its synth start. Existing engine log
  gives7630ms compute (5842ms token generation +1768ms decoder).
- Pi section0 plays13503→18427ms, WAV duration4.88s; section1 receives21219ms
  and player spawns21220ms. Gap:2793ms; receipt→spawn:1ms.
- Next synthesis exceeds the preceding audio by~2.75s, explaining the gap.
  This is not evidence of a multi-second player-restart delay. Delayed receipt of
  some small events reflects the synchronous playback callback and must not be
  reclassified as network latency.

The current one-request-at-a-time producer already overlaps the next section
with playback. Chatterbox's generation lock serializes syntheses; another worker
adds contention/queueing, without demonstrated earlier readiness. Buffering more
before starting playback delays first audio. Therefore **no active-path fix or
extra prefetch concurrency was introduced**. Current RTF>1 supports this limit;
gapless speech remains unaccepted. A new live-dialog optimization loop was not
run to replace the outstanding human check.

## Validation and immediately executable human check

New benchmark tests:2 passed (truncated PCM rejection; warm-only statistics and
required sample count). Ruff check/format passed for runner/tests. The default
system Python lacks pytest/Ruff; checks succeeded using the existing
`services/ai/.venv/Scripts/python.exe`, without installing anything. No Core/AI/
Satellite production code changed, so their prior full suites/builds were not
repeated. All24 benchmark WAVs passed structural validation. All seven services
were ready during the experiment. Pi diagnostic verified DNS, TCP, health,
401 without credentials and active installed units; installed-client session
probe opened an authenticated session, validated greeting WAV and closed it.
It neither opened the microphone nor played audio. These are not new human
dialogue/quality acceptance results.

From repository-root PowerShell:

```powershell
node infrastructure/dev-stack.mjs status
& infrastructure/dev/Probe-PiCore.ps1
& infrastructure/dev/Invoke-VeloraProbe.ps1 -Mode session -InstalledClient
Start-Process .run/dev-recovery/tts-isolated/listening.html
```

The normal `kyrion-voice-satellite.service` is active; no startup change is needed.
For diagnosis, this bounded SSH command uses the existing pinned host key:

```powershell
ssh.exe -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=yes -o HostKeyAlias=kyrion-node.local -i "$env:USERPROFILE/.ssh/kyrion_node_ed25519" flodinho@192.168.1.116 'systemctl --user is-active kyrion-voice-satellite.service; journalctl --user -u kyrion-voice-satellite.service -n 30 --no-pager'
```

1. On the Pi, say **Hey Velora**, then ask `Warum ist der Himmel blau? Antworte
   kurz.` Judge actual heard volume, German pronunciation, voice and meaning.
   Let inactivity close the session before the second wake.
2. Say **Hey Velora** again, then `Nenne drei Möglichkeiten, Wasser zu sparen.`
   Hear every item through its ending; note gaps, overlap, cut words and old audio.
   During playback try saying `Stopp` / `Hey Velora`; record actual behavior.
3. Source `dialogue.py:_run_session_once` captures input before synchronous
   `client.turn` and blocking `playback.play`. There is no concurrent capture/wake
   detector during playback: **spoken barge-in is not implemented**. The attempt
   documents that limitation; it is not an expected passing interruption test.
   Operator `-AbortDuringPlayback` tests technical cancellation only.
4. Use a local phone/video recording or stopwatch on one clock to mark end of
   spoken input and first **heard substantive answer**, excluding waiting audio.
   Report the measurement resolution (60fps~17ms), both dialogue times and section
   pauses separately from software invocation timestamps. Keep recordings local.
5. Listen to paired benchmark WAVs in the local page; compare complete words,
   accent, likeness and anomalies before considering any separate activation
   request. The candidate is not connected to the Satellite or active AI config.

No person supplied observations in this run. Wake detection, acoustic latency,
audibility, candidate acceptability and heard section continuity remain open.
Gateway destination/credential diagnosis still needs privileged access (the SSH
user cannot read its protected config or use passwordless sudo); prior journal
success is not proof of a new heartbeat in this Core DB. Full-host startup proof,
real-cloud acceptance/spending and V40 production rollout remain separate gates.
