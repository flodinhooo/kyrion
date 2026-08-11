# XTTS v2 multi-signal audio-code guard — 2026-08-11

## Decision

**B — XTTS v2 does not expose a sufficiently reliable completion signal for
dynamic Short outputs in the installed runtime. End this Short-optimisation
lane and continue with the proposed Fixed/Template/Dynamic architecture or a
separately measured Short-TTS path.**

None of the measured code-level signals independently confirmed the natural
pause after the requested phrase. Combining them therefore produced no stop in
any Short run. Relaxing the design to pause-only would repeat an already
rejected approach and would truncate a known clean Short output as well as both
Medium/Long controls.

This is an isolated, generation-free retrospective experiment. It changes no
Core, Satellite, provider adapter or production runtime behaviour. XTTS remains
experimental and opt-in, and all prior traces and WAVs remain preserved.

## Inputs and reproducibility

The runner `.run/xtts_multisignal_guard_retrospective.py` consumes:

- `/training/xtts-v2-eos-trace-v2/results.json` and its twelve WAVs;
- the matching ten period runs and whole-output word timestamps from
  `/training/xtts-v2-short-punctuation-matrix/results.json`;
- the ten fixed Short-DE seeds `50001`–`50010` plus one clean Medium-DE and one
  clean Long-DE control.

The period WAVs in both preserved datasets are byte-identical. The derived raw
result is `/training/xtts-v2-multisignal-retrospective.json`. It includes a
SHA-256 digest for every input WAV, every detected pause, all signal values,
candidate stop positions and classifications.

No new synthesis was needed for the retrospective evaluation. Faster-Whisper
was not run per chunk and is not a guard input. Existing whole-output word
timestamps are used only to label whether a proposed stop lies after the third
requested word and before the first extra word. Some later word timestamps
extend past the actual WAV duration, so those invalid late timestamps are
discarded.

## Measured signals

### Natural acoustic pause

The analysis detects at least 120 ms below -40 dBFS. A pause only creates an
evaluation point; it can never stop output by itself.

Retrospectively, the first qualifying pause ended inside the desired safe
window in seven Short runs. It ended before requested content was complete in
seeds `50003` and `50010`; seed `50008` never produced the requested phrase at
all. The Medium and Long controls contain ordinary internal pauses of 0.16–1.44
seconds. Pause duration therefore cannot distinguish completion from ordinary
prosody.

### EOS evidence

At every evaluated pause, effective EOS sampling probability was zero. EOS
rank ranged from 162 to 986 and was normally in the hundreds. The strongest
pause-aligned EOS probability was only `0.00031694`, during already
hallucinated output in seed `50002`; it still remained outside the sampling
set. EOS cannot independently confirm the otherwise useful early pauses.

### Repeated audio-code n-grams

No pause in any Short or control run ended with a suffix 2-, 3- or 4-gram that
had appeared earlier. The recent 24-code window also normally had zero repeated
bigrams; one later hallucinated pause had one. Linguistic fantasy speech is not
literal codec-token repetition in this corpus, so this signal provides no
completion boundary.

### Code-distribution entropy

The preserved trace contains the top ten sampling probabilities rather than
the complete distribution. The runner therefore records a bounded top-ten
entropy with the omitted probability mass represented as one residual bucket,
and compares it with the preceding 20-code median.

Pause-aligned entropy deltas overlap completely:

- hallucinating Short examples include approximately `-0.56`, `-0.17`,
  `+0.20` and `+0.75` bits;
- the one clean Short run has `-0.63` bits;
- clean controls include approximately `-0.38` through `+0.54` bits.

Neither falling entropy, rising entropy nor a 0.5-bit absolute change separates
completion from clean speech or internal pauses.

### Text attention/progress

Text attention was not present in the preserved traces. A bounded pilot tried
to request attention through the installed Coqui streaming generator. The
patched generator then called `GPT2InferenceModel.forward()` without the
`attention_mask` required by its incremental path and failed before producing
audio. The failed instrumentation was removed from the EOS runner and did not
modify the installed environment.

Obtaining the signal would require replacing or privately forking Coqui's
stream-generation loop. Even if a useful offline attention trace emerged, the
guard would then depend on an unstable private implementation path. That fails
the existing stop condition and is not proportionate after all observable
signals failed.

## Candidate results

Three deliberately small candidates were evaluated. Each requires a natural
pause plus at least one independent model/code signal:

| Candidate | Additional signals | Hallucination false negatives | Unrecoverable wrong-content run | Clean Short result | Medium/Long false positives |
| --- | --- | ---: | ---: | ---: | ---: |
| Pause + EOS | EOS rank ≤ 50 and probability ≥ 0.001 | 8/8 | 1/1 | correct no-stop | 0/2 |
| Pause + repeated n-gram | at least two matching suffix n-grams among sizes 2/3/4 | 8/8 | 1/1 | correct no-stop | 0/2 |
| Pause + repetition + entropy | repeated suffix n-gram and absolute entropy delta ≥ 0.5 bits | 8/8 | 1/1 | correct no-stop | 0/2 |

All three candidates made zero stops. They avoid truncation only because their
independent signals never confirm any pause; consequently they prevent none of
the eight post-content hallucinations. Seed `50008` is not guard-recoverable
because requested content is absent rather than followed by a detectable tail.

There is no plausible candidate to promote to new live generation or a wider
corpus. Adjusting thresholds cannot create n-gram or EOS evidence that is not
present, while entropy thresholds would overfit twelve runs and already overlap
the clean controls.

## Consequence

Stop the XTTS dynamic-Short completion work. Do not add an EOS bias, VAD-only
cut, per-chunk ASR, private attention fork or larger parameter matrix.

Retain XTTS as an opt-in experimental candidate for normal/longer text while
the product-level path proceeds separately:

- reviewed pre-rendered audio for fixed responses;
- typed localized templates and complete-utterance caching for trusted dynamic
  values;
- a separately benchmarked deterministic Short-TTS provider for remaining
  dynamic cache misses;
- normal provider-neutral TTS for unrestricted longer responses.

The existing `docs/voice-deterministic-responses-architecture.md` proposal
already describes this boundary. It remains a proposal and was not modified by
this experiment.

