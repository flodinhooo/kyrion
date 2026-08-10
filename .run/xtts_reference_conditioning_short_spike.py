"""Measure two same-voice conditioning excerpts against Short-DE runaway."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import soundfile as sf
from faster_whisper import WhisperModel
from TTS.api import TTS

BASE_PATH = Path(__file__).with_name("xtts_short_punctuation_matrix.py")
SPEC = importlib.util.spec_from_file_location("punctuation", BASE_PATH)
assert SPEC and SPEC.loader
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)

EXCERPTS = {
    "opening-5_64s": (0.0, 5.64, "opening statements; flatter introductory prosody"),
    "answer-7_46s": (2.86, 10.32, "longer answer; multi-sentence question prosody"),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("/mnt/e/Kyrion/Data/voice-training/xtts-v2-reference-conditioning-short"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if hashlib.sha256(base.REFERENCE.read_bytes()).hexdigest() != base.REFERENCE_SHA256:
        raise RuntimeError("canonical reference checksum mismatch")
    audio, rate = sf.read(base.REFERENCE)
    if rate != base.RATE:
        raise RuntimeError("unexpected reference rate")
    refs = {}
    for name, (start, end, prosody) in EXCERPTS.items():
        target = args.output / f"reference--{name}.wav"
        sf.write(target, audio[round(start * rate) : round(end * rate)], rate, subtype="PCM_16")
        refs[name] = {"path": str(target), "sourceStartSeconds": start, "sourceEndSeconds": end, "prosody": prosody, "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
    runtime = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cuda")
    model = runtime.synthesizer.tts_model
    aligner = WhisperModel("small", device="cpu", compute_type="int8")
    runs = []
    for name, metadata in refs.items():
        conditioning = model.get_conditioning_latents(audio_path=[metadata["path"]])
        list(model.inference_stream("Systemstart.", "de", *conditioning, stream_chunk_size=base.CHUNK_TOKENS, **base.PARAMETERS))
        (args.output / name).mkdir(parents=True, exist_ok=True)
        for seed in base.SEEDS:
            result = base.run(model, aligner, conditioning, "period", seed, args.output / name)
            result["reference"] = name
            runs.append(result)
    summary = {name: {"cleanEos": sum(item["cleanEos"] for item in runs if item["reference"] == name), "runs": len(base.SEEDS)} for name in refs}
    (args.output / "results.json").write_text(json.dumps({"canonicalReferenceSha256": base.REFERENCE_SHA256, "derivedReferences": refs, "runs": runs, "summary": summary}, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
