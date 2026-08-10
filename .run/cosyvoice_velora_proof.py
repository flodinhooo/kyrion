from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import torch
import torchaudio
from cosyvoice.cli.cosyvoice import AutoModel

MODEL = "/training/models/cosyvoice3-0.5b-2512"
REFERENCE = Path("/mnt/e/dev/Kyrion/kyrion/.run/velora-female-options/F_weiblich_klar.wav")
REFERENCE_SHA256 = "d2afdc5faa3fb6cc41756daaaac3db63c30679e3bcd3e87f6dab0055d08dad09"
PROMPT = (
    "You are a helpful assistant.<|endofprompt|>Guten Morgen. Ich bin Velora. "
    "Für heute stehen noch zwei Aufgaben auf deiner Liste. Möchtest du zuerst den "
    "Überblick hören, oder sollen wir direkt anfangen?"
)
PHRASES = [
    ("de", "Velora, schalte bitte die desk lamp im Gamingraum ein."),
    ("en", "Velora, turn on the desk lamp in the gaming room, please."),
]
OUTPUT = Path("/training/cosyvoice-velora-proof")


def main() -> None:
    if hashlib.sha256(REFERENCE.read_bytes()).hexdigest() != REFERENCE_SHA256:
        raise RuntimeError("Velora reference checksum mismatch")
    OUTPUT.mkdir(exist_ok=True)
    load_started = time.perf_counter()
    model = AutoModel(model_dir=MODEL, fp16=True, load_vllm=False, load_trt=False)
    load_seconds = time.perf_counter() - load_started
    conditioning_started = time.perf_counter()
    model.add_zero_shot_spk(PROMPT, str(REFERENCE), "velora-f")
    conditioning_seconds = time.perf_counter() - conditioning_started
    list(model.inference_zero_shot(
        "Systemstart abgeschlossen.", "", "", zero_shot_spk_id="velora-f", stream=True
    ))
    torch.cuda.reset_peak_memory_stats()
    results = []
    for locale, text in PHRASES:
        for repetition in range(3):
            started = time.perf_counter()
            chunk_times = []
            chunks = []
            for event in model.inference_zero_shot(
                text, "", "", zero_shot_spk_id="velora-f", stream=True
            ):
                chunk_times.append(time.perf_counter() - started)
                chunks.append(event["tts_speech"].detach().cpu())
            audio = torch.cat(chunks, dim=1)
            target = OUTPUT / f"velora-{locale}-{repetition + 1}.wav"
            torchaudio.save(str(target), audio, model.sample_rate)
            results.append({
                "locale": locale,
                "repetition": repetition + 1,
                "text": text,
                "firstAudioSeconds": round(chunk_times[0], 3),
                "totalSeconds": round(time.perf_counter() - started, 3),
                "chunkTimesSeconds": [round(value, 3) for value in chunk_times],
                "audioSeconds": round(audio.shape[1] / model.sample_rate, 3),
                "chunks": len(chunks),
                "wav": str(target),
            })
    report = {
        "model": MODEL,
        "referenceSha256": REFERENCE_SHA256,
        "loadSeconds": round(load_seconds, 3),
        "conditioningSeconds": round(conditioning_seconds, 3),
        "sampleRate": model.sample_rate,
        "peakAllocatedVramMiB": round(torch.cuda.max_memory_allocated() / 2**20, 1),
        "results": results,
    }
    (OUTPUT / "proof.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
