# XTTS v2 short-output optimisation plan — 2026-08-12

## Objective and boundary

Continue XTTS v2 only as an isolated MVP candidate and investigate the
reproducible hallucinations after very short outputs. Do not add or change a
Core integration, provider adapter, physical Satellite path or default provider
as part of this plan.

Keep native 20-token XTTS streaming as the control for ordinary and longer
answers. Do not repeat the punctuation grid, broad decoding searches or the
already rejected VAD-only and per-chunk Faster-Whisper guards.

Acceptance remains conjunctive:

- Short DE at least 19/20 correct with no audible fantasy speech;
- Medium, Long, Dialogue, Numbers and Domain DE/EN complete;
- warm TTFA P95 at most 1 second;
- Long RTF below 0.90;
- zero playback underruns;
- no pronunciation or prosody regression.

## Priority 1: instrument XTTS EOS directly

Inspect the autoregressive audio-code generator rather than inferring semantic
completion from the finished waveform. Record for every generated audio code:

- probability and rank of the loaded model's declared audio EOS token. Direct
  inspection subsequently established `gpt.stop_audio_token == 1025` with
  1,026 output logits; `8193` was not valid for this installed output layer;
- top-k token IDs and probabilities;
- margin between EOS and the selected token;
- generated-code position and elapsed audio duration;
- text-token count and any available text-progress or attention state;
- whether the final output was clean, hallucinated or truncated.

Run the same ten Short-DE seeds for the normal period input and enough clean
Medium/Long controls to compare EOS traces. The main question is whether EOS
becomes consistently competitive after the requested content but loses to a
non-EOS token in hallucinating runs.

If EOS is not observable through a public hook, use an isolated, reversible
instrumentation patch in the benchmark environment. Do not copy private model
internals into runtime or provider code.

## Priority 2: inspect text tokenisation and terminal representation

The measured `?` result improved clean EOS from 1/10 to 8/10, so inspect the
actual GPT text input for `.`, `!`, `?` and `;`:

- exact token IDs and token count;
- final text token and explicit/implicit start/end tokens;
- padding or minimum-sequence behaviour for very short input;
- differences between the public XTTS API and the internal GPT call;
- Unicode normalisation and whitespace after preprocessing.

Look for a neutral internal completion representation that preserves
declarative prosody. Do not ship question punctuation as a workaround: it
changes meaning/prosody and already fails latency and correctness gates.

## Priority 3: bounded Short-only decoding experiments

Only if EOS traces show a plausible intervention point, compare a very small
set of Short-only decoding strategies using the same seeds:

1. deterministic decoding without sampling;
2. one low-temperature profile;
3. a conservative EOS logit bias or custom `LogitsProcessor`;
4. optionally, bounded beam search whose scoring prefers a credible EOS.

Do not combine several parameters into a grid. Each candidate must first reach
at least 19/20 Short-DE outputs before earning the full control corpus.

An EOS rule must include a plausible minimum generated duration/code count and
must not force termination solely because the text is short. Record whether EOS
was native or policy-forced.

## Priority 4: investigate an audio-code-level semantic guard

If EOS alone is insufficient, test whether cheap model-internal signals can
identify post-content degeneration without ASR:

- completion of text-token attention/progress;
- repeated audio-code n-grams;
- falling or abnormal code entropy;
- long generation without further text progress;
- EOS probability combined with a natural acoustic pause.

A guard may stop only when multiple independent signals agree. It must be
tested against natural pauses, numbers, names, `Velora`, `Gamingraum`, mixed
`desk lamp` terms and both languages. A VAD pause by itself is explicitly
insufficient; the existing test cut 10/20 Short outputs incorrectly.

## Priority 5: controlled conditioning reference

The two derived Velora-F excerpts achieved only 0/10 and 2/10 clean Short EOS.
Do not test more arbitrary crops. If conditioning remains a hypothesis, create
at most one purpose-built DE and one EN reference clip of the same voice:

- 6–12 seconds;
- one language per clip;
- steady pace and declarative prosody;
- phonetically varied text;
- no long internal pause, music or room noise;
- clean natural ending.

Hash and preserve each clip and its transcript. First run only the same ten
Short-DE seeds. Continue to the full corpus only after a material improvement.

## Priority 6: practical fallback designs

If XTTS cannot expose a reliable semantic completion signal, compare these
product-level alternatives outside Core:

### Verified prerendered short phrases

Use reviewed Velora-F audio for frequent fixed responses such as acknowledgments,
`yes`, `no`, `done` and identity phrases. This provides immediate playback,
zero hallucination risk and no GPU work, but must not pretend to support dynamic
names, numbers or device states.

### Separate lightweight Short-TTS candidate

Evaluate a deterministic, low-latency DE/EN TTS only for empirically short
dynamic replies while keeping XTTS native for longer answers. Require adequate
Velora identity, correct termination and the same pronunciation corpus. Keep
routing provider-neutral and isolated during evaluation.

### Generate-then-validate Short output

Measure full Short generation followed by Tiny ASR/VAD validation and a bounded
retry or fallback before audio release. Reject this design immediately if warm
end-to-end first playable audio cannot remain below one second. Never play a
fallback after faulty XTTS audio has already become audible.

## Emergency code budget

Retain the empirical character/punctuation model only as a generous final cost
and runaway bound:

```text
ceil_to_20(1.50 * (40.962 + 1.520 * alnum_chars
                   + 7.642 * punctuation_breaks) + 41.737)
```

It was fitted from clean, normally terminating XTTS controls with 50% reserve,
the largest positive fit residual and 20-code rounding. Observed regular output
uses at most 71.3% of its cap. The formula is not an EOS detector and must not
be used to certify semantic completion. The only measured control point remains
XTTS's private and unstable `model.gpt.max_gen_mel_tokens` field.

## Parallel execution lanes

These lanes can run independently tomorrow without modifying Core:

- **Lane A — EOS evidence:** instrument logits, EOS rank and code/text progress;
- **Lane B — tokenisation:** compare exact preprocessed text-token sequences and
  identify a neutral declarative completion representation;
- **Lane C — conditioning:** produce and test the two controlled DE/EN reference
  clips only if suitable source generation is available;
- **Lane D — fallback feasibility:** inventory or benchmark prerendered phrases,
  a lightweight Short-TTS candidate and held-audio validation latency.

Only Lane A results may authorise the bounded decoding experiments. Merge all
lane evidence into one decision table before any additional full corpus run.

## Stop conditions and decision

Stop a strategy when any of the following is established:

- fewer than 19/20 correct Short-DE runs;
- audible fantasy speech or truncated requested content;
- TTFA P95 above one second;
- any control-corpus completeness or prosody regression;
- Long RTF at or above 0.90;
- any underrun;
- dependence on an unstable private hook without a contained replacement plan.

The highest-information next experiment is direct EOS/logit and text-progress
instrumentation. It should determine whether XTTS can be repaired with a small,
principled Short-only policy or whether Short replies require a separate,
deterministic path.

Related evidence:

- [Short-output follow-up](2026-08-11-xtts-v2-short-output-follow-up.md)
- [Guard optimisation spike](2026-08-11-xtts-v2-guard-optimization-spike.md)
- [Streaming TTS acceptance criteria](../voice-tts-spike-acceptance.md)
