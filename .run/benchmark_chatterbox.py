import time

import torchaudio as ta
from chatterbox.mtl_tts import ChatterboxMultilingualTTS

REFERENCE = "/mnt/e/dev/Kyrion/kyrion/.run/velora-character-candidates/D_vertraute_begleiterin.wav"
OUTPUT = "/mnt/e/dev/Kyrion/kyrion/.run/chatterbox-velora-benchmark.wav"

started = time.perf_counter()
model = ChatterboxMultilingualTTS.from_pretrained(device="cuda")
print(f"model_load_seconds={time.perf_counter() - started:.3f}", flush=True)

model.prepare_conditionals(REFERENCE)
model.generate("Systemstart.", language_id="de")

for index, (text, cfg_weight) in enumerate(
    (
        ("Ich bin Velora und begleite dich durch deinen Alltag.", 0.5),
        ("Ich bin Velora und begleite dich durch deinen Alltag.", 0.0),
    ),
    1,
):
    started = time.perf_counter()
    wav = model.generate(text, language_id="de", cfg_weight=cfg_weight)
    elapsed = time.perf_counter() - started
    print(f"generation_{index}_seconds={elapsed:.3f} samples={wav.shape[-1]}", flush=True)
    ta.save(OUTPUT.replace(".wav", f"-{index}.wav"), wav.cpu(), model.sr)
