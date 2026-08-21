# Voice action processing feedback — 2026-08-21

## Result

Core now emits a fixed `action.processing` response only after a device action
proposal has been recognized and validated. It revalidates the active Voice
session after emitting the response and before invoking the action execution
service. The processing response never represents success; the real confirmed
action outcome still produces the final success or failure response.

The owner listened to two Qwen3-TTS 1.7B Velora candidates for each new line
and approved four German processing variants and four additional German
greetings. Only the selected mono PCM16 24 kHz WAVs were registered in the
checksum-pinned production manifest. Non-selected candidates remain private
review material outside Git. English catalog entries are present but remain
pending assets.

## Processing variants

- `Klar, gib mir einen Augenblick.`
- `Alles klar, ich kümmere mich darum.`
- `Verstanden, einen Moment bitte.`
- `Gerne, ich kümmere mich darum.`

## Verification

- complete Core test suite passed;
- AI suite: 106 tests passed and Ruff passed;
- all 16 generated review WAVs passed mono PCM16/24 kHz validation;
- Parakeet produced the intended wording for all generated candidates;
- all four registered processing variants resolved from the running AI service
  as HTTP 200 RIFF/WAV responses;
- AI and Core health checks passed after restart.
