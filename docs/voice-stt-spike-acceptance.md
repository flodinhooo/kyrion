# Streaming STT spike acceptance

This document defines the comparison gate for future local streaming speech-to-
text candidates. A lower aggregate word error rate (WER) is useful diagnostic
evidence, but it is not sufficient to replace Kyrion's current Faster-Whisper
`small/int8` final-transcript baseline.

## Fixed comparison basis

Every candidate must run against the preserved private 150-second Delock
recording and the same 20 speech plus six silence/noise clips. German and
English must use the explicit session locale. Results must retain per-clip
final text, timestamped partials and resource samples outside Git.

Additional recordings may extend a spike, but must be reported separately and
must not replace or alter the fixed comparison set. The next extended set must
include a natural interrupted self-correction such as `Wohn– nein,
Gamingraum`, rather than a synthetic splice.

## Weighted recognition score

Score an aligned reference/hypothesis token substitution, deletion or insertion
with the highest applicable weight:

| Token or semantic role | Weight | Examples |
| --- | ---: | --- |
| Kyrion/domain identity | 5 | `Velora`, configured room names, configured device names, `desk lamp` |
| Intent and correction control | 3 | `ein`, `aus`, `stop`, negation, correction target and superseded target |
| Parameters and state | 2 | brightness, percentage, temperature, time and availability |
| Ordinary language | 1 | remaining words |

Report both ordinary WER and weighted error rate. For multi-token entity names,
score the entity as one semantic unit as well as retaining the token-level
diagnostic. A recognisable sentence with the wrong room, device, polarity or
action is not a usable command.

Manual sentence review classifies each final as `correct`, `usable`,
`ambiguous` or `wrong`. Review must explicitly record assistant-name, room,
device, action, negation and correction-target preservation. The machine score
supports this review; it does not override unsafe meaning changes.

## Hard gates

A candidate is ineligible for integration if any of these fail:

- all six fixed silence/noise clips produce empty finals;
- explicit `de-DE` and `en-US` operation is stable, without per-clip automatic
  language switching;
- no regression from the baseline on `Velora`, room/device identity, action,
  negation or final correction target;
- partials are clearly non-authoritative and the final represents the latest
  spoken correction rather than a superseded command;
- P95 end-of-speech-to-final latency is below 1.0 second on the target local
  hardware, without an accumulating queue;
- streaming state, memory and request counts remain bounded during repeated
  turns, disconnect and reconnect;
- cancellation stops new inference/output within 250 ms and emits no later
  partial or final for the cancelled turn;
- CPU, RAM and any VRAM are measured, and a GPU candidate leaves at least 2 GiB
  of measured peak headroom on the 8 GiB reference GPU;
- runtime and model licences, exact versions/checksums and local data flow are
  recorded before any production planning.

## Clear-win replacement gate

Passing the hard gates only makes a candidate eligible. Replacing
Faster-Whisper `small/int8` additionally requires all of the following on the
same fixed set:

- at least two more `correct` or `usable` sentence meanings than the baseline;
- at least 20% relative reduction in weighted error rate;
- no worse ordinary WER by more than one percentage point;
- materially better streaming latency than the baseline, including useful
  partials and authoritative final latency;
- no new critical domain-term or correction regression in manual review.

If the sample is too small to establish a clear win, the result remains a
documented spike rather than an integration candidate. Provider-specific word
boosting or catalogue context may be evaluated only as a separately reported
configuration and must not silently guess an ambiguous Core action.

