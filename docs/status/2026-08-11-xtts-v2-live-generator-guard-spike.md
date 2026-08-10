# XTTS v2 live-generator guard spike — 2026-08-11

## Decision

XTTS v2 is **NO-GO for integration on the current MVP hardware and runtime**.
No provider adapter or Core integration was added.

The subsequent bounded guard-optimisation spike confirms this decision after
measuring VAD gating, incremental tails, Tiny alignment and an internal XTTS
code-length cap; see `2026-08-11-xtts-v2-guard-optimization-spike.md`.

The live guard successfully prevents the known Short-DE pseudo-speech from
reaching its simulated player, but local Faster-Whisper `small/int8` alignment
on every native 20-token XTTS chunk is far too slow. It raises first playable
PCM to 2.86–3.52 seconds, produces RTF 1.61–3.25 and causes playback underruns
in 13 of 19 runs. This fails the existing latency, sustained-throughput and
continuous-playback hard gates.

## Live architecture

The isolated runner attaches directly to XTTS `inference_stream()`. XTTS runs
in a producer thread on CUDA while Faster-Whisper runs on CPU. A bounded queue
permits one generated lookahead chunk. The guard:

- incrementally transcribes the actual accumulated PCM at each XTTS yield;
- aligns it against the known input without a language-word whitelist;
- retains the newest unverified XTTS chunk;
- after complete-content alignment, requires 300 ms below -40 dBFS and retains
  200 ms of trailing silence;
- signals cancellation between XTTS yields, drains/discards queued lookahead
  and never releases PCM after its decision.

Generated, guard-buffered and playable-released PCM are measured separately.
Playback uses the shared 320 ms prebuffer simulation.

## Matrix

Ten seeded `Ich bin Velora.` turns deliberately exercise the probabilistic
failure. One run each covers Medium DE, Long DE, Dialogue DE, Numbers DE/EN,
Domain DE/EN and adversarial DE/EN texts with a natural internal pause, names
and mixed `desk lamp`/`Gamingraum` terms.

All ten Short-DE outputs receive a live guard decision and their retained WAVs
transcribe only as `Ich bin Velora.` in nine cases and `Ich bin Veloda.` in one.
No pseudo-speech escapes. Decision happens at 2.86–4.30 seconds and generator
cancellation completes at 2.86–4.94 seconds. XTTS can finish another 0–0.928
seconds of lookahead PCM after the decision, but that PCM is discarded;
post-decision released PCM is exactly zero in every run. At decision time XTTS
has already generated 2.411–4.597 seconds of PCM, of which only 1.200–2.420
seconds is released as playable. The remaining 1.011–2.817 seconds is held in
the consumer, bounded queue or producer lookahead and discarded. A further
0–0.928 seconds can complete after the decision before cancellation reaches the
next generator yield; it is also discarded.

The non-short and adversarial cases are not cut. Their final probe transcripts
preserve the intended content, subject to the already known pronunciation/ASR
variants for `desk lamp`, `Gamingraum` and names. Natural internal pauses do
not trigger the guard.

## Performance failure

| Metric | Result | Required |
| --- | ---: | ---: |
| Guard ASR median per check | 1.16–1.44 s | must fit streaming cadence |
| Guard ASR P95 per run | 1.23–1.56 s | must not drain prior PCM |
| Short guarded TTFA | 2.86–3.52 s | P95 <= 2.0 s, target <= 1.0 s |
| Full-matrix RTF | 1.61–3.25 | long-form < 0.90 |
| Playback underruns | 13/19 runs affected | zero |
| Post-decision released PCM | 0 s in every short run | zero |

The one-chunk safety holdback is necessary to prevent already generated
pseudo-speech from becoming audible. With the measured 1.2–1.5 second ASR
checks, that holdback starves playback. Releasing it earlier would improve
latency but violate the central correctness requirement. The guard therefore
cannot be repaired by queue tuning without changing the safety property.

## Scope and evidence

This decision rejects the measured XTTS plus Faster-Whisper live-guard design
for the current MVP. It does not claim that future hardware or a genuinely
low-latency acoustic/text-alignment mechanism could never make XTTS usable.
Such a different guard is a new candidate, not an integration task.

- runner: `.run/xtts_live_generator_guard_spike.py`
- private results and listening WAVs:
  `E:/Kyrion/Data/voice-training/xtts-v2-live-guard-review/`
- raw event detail: `results.json`
- independent final probes: `quality-transcripts.json`
