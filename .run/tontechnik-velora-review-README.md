# Velora listening comparison for sound-engineering review

This folder contains copies of existing evidence. Originals remain unchanged.
Nothing in this folder is a production asset.

## 01_reference_and_accepted

- `01_velora-f_canonical-reference.wav`: immutable Velora-F conditioning
  reference and the clearest statement of the intended timbre.
- `02_qwen_de_owner-liked.wav`: German domain sentence; owner judged this
  short Qwen sample good.
- `03_qwen_en_owner-liked.wav`: English domain sentence; owner judged this
  sample good, with understandable but improvable pronunciation of `Velora`.

## 02_good_longer_examples

These stock XTTS v2 medium/long examples retained the intended words and are
useful for discussing timbre, prosody and why Velora works better on longer
material:

- `01_xtts_medium_de_clean.wav`: "Ich bin Velora und begleite dich durch deinen Alltag."
- `02_xtts_long_de_clean.wav`: longer natural German answer.
- `03_xtts_dialogue_de_clean.wav`: longer German factual dialogue answer.

## 03_problem_examples

- `01_xtts_short_fantasy-speech.wav`: correct "Ich bin Velora." followed by
  several seconds of pseudo-language.
- `02_fixed_de_farewell_fantasy-speech.wav`: requested "Bis später." with
  owner-confirmed fantasy words.
- `03_fixed_de_greeting_bad-ending.wav`: warm greeting with substantial
  owner-confirmed fantasy speech at the ending.
- `04_piper_wrong-voice-quality.wav`: terminates quickly, but timbre and overall
  quality are not acceptable as Velora.
- `05_chatterbox_poor-voice-and-repetition.wav`: rejected Velora identity and
  quality; the domain sample also contains an unwanted repetition.

## Questions for the discussion

1. Which acoustic properties make the canonical reference and accepted samples
   read as the same person?
2. Can twelve short fixed sentences be recorded consistently from one human
   performance without making them sound like isolated prompts?
3. What loudness, peak, leading-silence and trailing-silence targets should be
   used across all twelve final mono PCM16/24 kHz assets?
4. Should greetings, acknowledgements and farewells use different energy while
   retaining one stable voice identity?
