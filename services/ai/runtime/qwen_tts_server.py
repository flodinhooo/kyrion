"""Persistent local Qwen TTS runtime for Kyrion development."""

from __future__ import annotations

import argparse
import io
import threading
from pathlib import Path

import soundfile as sf
import torch
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field
from qwen_tts import Qwen3TTSModel

MODEL_PATH = "/training/models/qwen3-tts/voice-clone-base"
VOICE_ROOT = Path("/mnt/e/dev/Kyrion/kyrion/.run")
VOICES = {
    "velora": (
        "Velora",
        VOICE_ROOT / "velora-character-candidates/D_vertraute_begleiterin.wav",
        "Guten Abend. Ich bin Velora. Das Licht im Wohnzimmer ist noch eingeschaltet. "
        "Soll ich es dimmen, oder möchtest du den Raum lieber genauso lassen?",
    ),
    "klar": (
        "Klar",
        VOICE_ROOT / "velora-female-options/F_weiblich_klar.wav",
        "Guten Morgen. Ich bin Velora. Für heute stehen noch zwei Aufgaben auf deiner Liste. "
        "Möchtest du zuerst den Überblick hören, oder sollen wir direkt anfangen?",
    ),
    "sanft": (
        "Sanft",
        VOICE_ROOT / "velora-female-options/H_weiblich_sanft.wav",
        "Guten Morgen. Ich bin Velora. Für heute stehen noch zwei Aufgaben auf deiner Liste. "
        "Möchtest du zuerst den Überblick hören, oder sollen wir direkt anfangen?",
    ),
    "elegant": (
        "Elegant",
        VOICE_ROOT / "velora-female-options/J_weiblich_elegant.wav",
        "Guten Morgen. Ich bin Velora. Für heute stehen noch zwei Aufgaben auf deiner Liste. "
        "Möchtest du zuerst den Überblick hören, oder sollen wir direkt anfangen?",
    ),
}


class SynthesisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4_000)
    voice_id: str = Field(alias="voiceId")


app = FastAPI(title="Kyrion Local Qwen TTS", version="0.1.0")
model: Qwen3TTSModel | None = None
prompts: dict[str, object] = {}
generation_lock = threading.Lock()


@app.on_event("startup")
def load_runtime() -> None:
    global model
    model = Qwen3TTSModel.from_pretrained(
        MODEL_PATH,
        device_map="cuda:0",
        dtype=torch.float16,
        attn_implementation="sdpa",
    )
    for voice_id, (_, reference, transcript) in VOICES.items():
        if not reference.is_file():
            raise RuntimeError(f"Missing reference voice: {voice_id}")
        prompts[voice_id] = model.create_voice_clone_prompt(
            ref_audio=str(reference), ref_text=transcript
        )


@app.get("/health")
def health() -> dict[str, object]:
    return {"status": "ready" if model is not None else "loading", "voices": len(prompts)}


@app.get("/v1/voices")
def voices() -> dict[str, object]:
    return {
        "defaultVoiceId": "velora",
        "voices": [
            {"id": voice_id, "name": name, "locale": "de-DE", "gender": "female"}
            for voice_id, (name, _, _) in VOICES.items()
        ],
    }


@app.post("/v1/synthesize")
def synthesize(request: SynthesisRequest) -> Response:
    if model is None:
        raise HTTPException(status_code=503, detail="TTS_LOADING")
    prompt = prompts.get(request.voice_id)
    if prompt is None:
        raise HTTPException(status_code=400, detail="UNKNOWN_VOICE")
    with generation_lock:
        wavs, sample_rate = model.generate_voice_clone(
            text=request.text,
            language="German",
            voice_clone_prompt=prompt,
            max_new_tokens=2_048,
        )
    output = io.BytesIO()
    sf.write(output, wavs[0], sample_rate, format="WAV")
    return Response(output.getvalue(), media_type="audio/wav")


def main() -> None:
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", default=8010, type=int)
    arguments = parser.parse_args()
    uvicorn.run(app, host=arguments.host, port=arguments.port)


if __name__ == "__main__":
    main()
