import time
from pathlib import Path

import torchaudio as ta
from chatterbox.mtl_tts import ChatterboxMultilingualTTS

ROOT = Path("/mnt/e/dev/Kyrion/kyrion/.run")
OUTPUT = ROOT / "chatterbox-final-voice-clones"
OUTPUT.mkdir(exist_ok=True)

VOICES = {
    "D_vertraute_begleiterin": ROOT / "velora-character-candidates/D_vertraute_begleiterin.wav",
    "F_weiblich_klar": ROOT / "velora-female-options/F_weiblich_klar.wav",
    "H_weiblich_sanft": ROOT / "velora-female-options/H_weiblich_sanft.wav",
    "J_weiblich_elegant": ROOT / "velora-female-options/J_weiblich_elegant.wav",
}
TEXT = "Ich bin Velora und begleite dich durch deinen Alltag. Was möchtest du als Nächstes gemeinsam angehen?"

started = time.perf_counter()
model = ChatterboxMultilingualTTS.from_pretrained(device="cuda")
print(f"model_load_seconds={time.perf_counter() - started:.3f}", flush=True)

first_reference = next(iter(VOICES.values()))
model.prepare_conditionals(str(first_reference), exaggeration=0.45)
model.generate("Systemstart.", language_id="de", cfg_weight=0.5)

for voice_id, reference in VOICES.items():
    model.prepare_conditionals(str(reference), exaggeration=0.45)
    started = time.perf_counter()
    wav = model.generate(
        TEXT,
        language_id="de",
        cfg_weight=0.5,
        temperature=0.65,
        repetition_penalty=2.0,
    )
    elapsed = time.perf_counter() - started
    target = OUTPUT / f"{voice_id}.wav"
    ta.save(str(target), wav.cpu(), model.sr)
    print(f"{voice_id} seconds={elapsed:.3f} path={target}", flush=True)
