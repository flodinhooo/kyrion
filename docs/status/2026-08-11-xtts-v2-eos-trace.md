# XTTS v2 direct EOS trace — 2026-08-11

## Decision

Direct autoregressive evidence does **not** support an EOS logit bias as the
next Short-DE intervention. In the installed Coqui XTTS 0.22 runtime, EOS was
normally excluded by the existing top-k/top-p policy until the generator had
already produced the unwanted continuation. The subsequent terminal-token
comparison also found no neutral completion representation. Do not attempt a
decoding change on the basis of this evidence.

This remains an isolated benchmark result. It does not authorise a Core,
provider-adapter, Satellite or default-provider change.

## Runtime correction

The loaded model reports `gpt.stop_audio_token == 1025` and
`gpt.num_audio_tokens == 1026`. The previously documented value `8193` is not
an audio-token ID in this installed output layer: its logits have only 1,026
entries. All measurements therefore use the model-declared stop token rather
than a copied constant.

## Method

`.run/xtts_eos_trace_spike.py` attaches a reversible Hugging Face
`LogitsProcessor` to the isolated generator. It does not patch the installed
library on disk. For every generated code it records:

- model-declared EOS probability and rank after repetition processing and
  temperature;
- effective EOS sampling probability after reconstructed top-k/top-p warping;
- selected token, selected-token probability and the EOS/selection margin;
- top ten sampled tokens, code position, wall-clock time and estimated audio
  position;
- exact preprocessed text tokens plus explicit text start/stop tokens;
- generated WAV, duration and an independent Faster-Whisper transcript.

The run repeated the existing Short-period seeds `50001` through `50010` and
added one Medium-DE and one Long-DE control. Raw JSON and listening WAVs are
stored under `/training/xtts-v2-eos-trace-v2/` in the dedicated
`Kyrion-Voice-Training` WSL distribution and are not committed.

## Results

All twelve runs selected native EOS eventually. The ten Short runs generated
46–169 audio codes and 2.091–7.797 seconds of audio. Independent ASR reproduced
the known failure shape: only seed `50009` ended at `Ich bin Velora`; the other
runs added words, changed the requested phrase or produced a longer fantasy
continuation. These labels remain machine evidence until the WAVs receive a
listening classification.

Before the final generation step:

- 9/10 Short runs gave EOS zero effective sampling probability at every code;
- seed `50010` gave EOS non-zero sampling probability once, at position 108 of
  110, immediately before native completion rather than after the requested
  phrase;
- seeds `50004` and `50008` briefly ranked EOS in the top ten only at positions
  97/99 and 167/169, again immediately before native completion;
- the Medium and Long controls gave EOS zero effective sampling probability
  before their final code;
- final EOS probability was 0.748–1.000 for Short, 1.000 for Medium and 0.565
  for Long after temperature, and final effective sampling probability was
  0.770–1.000.

The trace therefore rejects the working hypothesis that EOS becomes
consistently competitive after the requested Short content but merely loses a
close sampling decision. Under the current policy, the model usually does not
offer EOS as a sampleable candidate at that boundary.

## Next bounded step

The terminal-token probe found no hidden completion representation. All four
inputs are lower-cased and otherwise preserved, then receive text start token
`261` and text stop token `0`. They have the same nine content-token positions;
only the final punctuation token changes: `.` → `9`, `!` → `3`, `?` → `13`
and `;` → `12`. `compute_embeddings()` adds the same explicit start/stop
padding for every case. `inference_stream()` strips surrounding whitespace
before tokenisation, so trailing spaces do not add a terminal token.

The question mark's earlier 8/10 result therefore reflects a learned
punctuation-token effect, not an extra EOS marker or different sequence length.
There is no evidence for a neutral declarative completion token to substitute.
Do not ship question punctuation or broaden the decoding matrix.

The next code-level experiment should not be an EOS bias: this lane did not
find the plan's required plausible intervention point. Compare the remaining
bounded product-level alternatives or investigate a multi-signal audio-code
guard only if it can locate requested-content completion independently of EOS.

Before using the trace as final quality evidence, listen to and classify all
ten Short WAVs as clean, hallucinated or truncated. If that review contradicts
the ASR result, update this report rather than silently changing the labels.
