# XTTS v2 reproducible short-output follow-up — 2026-08-11

## Decision

XTTS v2 remains an open experimental candidate, but it is **not accepted for
integration**. No Core integration or provider adapter was added by this
follow-up. The reproducible Short-DE hallucination still fails the requested
19/20 correctness gate, and no measured lightweight hybrid preserves both
content and runtime gates.

## Bounded punctuation and normalisation matrix

The matrix uses native 20-token streaming, the canonical Velora-F reference and
the same ten seeds for four unique terminal forms. Missing punctuation,
trailing whitespace, NFD input and duplicate punctuation are normalised and
deduplicated when they resolve to the same model text.

Clean EOS means exact normalised `small/int8` ASR words and no more than 600 ms
of >= -40 dBFS activity after the expected final word.

The Coqui alias reported an update and refreshed its local model cache before
this matrix. These results therefore form a new internally consistent run and
must not be treated as bit-identical continuation of the earlier snapshot. The
private runtime manifest records `TTS 0.22.0`, PyTorch 2.1.2+cu121,
Transformers 4.36.2 and SHA-256 hashes for the current model, config, vocabulary
and speaker files.

| Terminal | Clean EOS | TTFA P95 | Max RTF | Underruns |
| --- | ---: | ---: | ---: | ---: |
| `.` | 1/10 | 0.630 s | 0.734 | 0 |
| `!` | 0/10 | 0.731 s | 0.821 | 0 |
| `?` | 8/10 | 1.546 s | 1.916 | 0 |
| `;` | 0/10 | 0.711 s | 0.806 | 0 |

The question mark materially improves termination but still emits an extra
`Was?` in one run, changes `Velora` to `Veloura` in another, and has one 2.060 s
TTFA outlier. Converting declarative answers into questions is itself an
unacceptable prosody/meaning change.

The required control pass preserved Medium/Long/Dialogue/Numbers content and
recorded 0 underruns. Long RTF was 0.656. Domain DE/EN still reproduced the
known `Gammingraum` and `Villora` pronunciation defects. The question variant
therefore does not qualify despite its stronger Short termination.

## Conditioning sensitivity

Two separately hashed excerpts were derived from the immutable canonical
recording without overwriting it: a 5.64 s introductory excerpt and a 7.46 s
multi-sentence/question-prosody excerpt. Against the same ten period-terminated
Short-DE seeds they achieved respectively 0/10 and 2/10 clean EOS. Conditioning
changes the random outcome but does not remove the failure.

## Hybrid guard result

Normal and longer text remains native XTTS by design. For Short only, a cheap
VAD stop detected the first 300 ms pause after at least 450 ms active speech and
retained 200 ms natural silence. It achieved TTFA <= 0.721 s and 0 underruns,
but only 10/20 transcripts were correct because natural micro-pauses can occur
before semantic completion. VAD alone is unsafe.

The previously measured VAD + Tiny semantic guard has better tail recall but
causes playback underruns and long-form RTF above the gate. Retry/fallback after
ASR would have to hold the Short audio until validation and therefore cannot
meet the <= 1 s first-playable target on this runtime. No hybrid variant passes
all gates together.

## Empirical emergency code budget

The old `max(48, 14 * words)` formula is rejected. A reproducible fit uses clean
native non-Short outputs, removes three gross non-terminating outliers above
1.25 times their phrase median, estimates audio-code use from 1,024-sample code
frames, and fits characters plus punctuation breaks:

```text
ceil_to_20(1.50 * (40.962 + 1.520 * alnum_chars
                   + 7.642 * punctuation_breaks) + 41.737)
```

The 1.50 multiplier, largest positive fit residual and 20-code rounding make it
a deliberately generous emergency brake. Clean controls use at most 71.3% of
their cap. `Ich bin Velora.` receives 160 codes (nominally 6.827 s), so the cap
cannot classify clean Short output and is not a semantic guard. It only bounds
extreme runaway cost through XTTS's private, unstable
`model.gpt.max_gen_mel_tokens` field.

## Acceptance result

| Gate | Result |
| --- | --- |
| Short DE >= 19/20, no fantasy speech | **Fail**; best punctuation 8/10, VAD hybrid 10/20 |
| Medium/Long/Dialogue/Numbers/Domain complete | Content controls complete; known Domain pronunciation defects remain |
| TTFA P95 <= 1 s | **Fail** for question variant (1.546 s); VAD hybrid passes |
| Long RTF < 0.90 | Pass, 0.656 in the question control |
| 0 underruns | Pass in the new matrices; Tiny semantic guard previously fails |

The acceptance conjunction is not met. Keep XTTS isolated and make no
integration decision until a different semantic-progress mechanism or runtime
can meet every gate.

Evidence:

- `.run/xtts_short_punctuation_matrix.py`
- `.run/xtts_question_validation.py`
- `.run/xtts_reference_conditioning_short_spike.py`
- `.run/xtts_short_vad_hybrid_spike.py`
- `.run/xtts_code_budget_fit.py`
- private WAVs and JSON under
  `E:/Kyrion/Data/voice-training/xtts-v2-short-punctuation-matrix/`,
  `xtts-v2-question-validation/`, `xtts-v2-reference-conditioning-short/` and
  `xtts-v2-short-vad-hybrid/`; runtime hashes are in
  `xtts-v2-runtime-manifest-2026-08-11.json`
