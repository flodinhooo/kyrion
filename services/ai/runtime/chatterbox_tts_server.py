"""Persistent Chatterbox TTS runtime using Velora's selected F voice."""

from __future__ import annotations

import argparse
import io
import threading

import soundfile as sf
from chatterbox.mtl_tts import ChatterboxMultilingualTTS
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field

REFERENCE = "/mnt/e/dev/Kyrion/kyrion/.run/velora-female-options/F_weiblich_klar.wav"


class SynthesisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4_000)
    voice_id: str = Field(alias="voiceId")


app = FastAPI(title="Kyrion Local Chatterbox TTS", version="0.1.0")
model: ChatterboxMultilingualTTS | None = None
generation_lock = threading.Lock()


@app.on_event("startup")
def load_runtime() -> None:
    global model
    model = ChatterboxMultilingualTTS.from_pretrained(device="cuda")
    model.prepare_conditionals(REFERENCE, exaggeration=0.45)
    model.generate("Systemstart.", language_id="de", cfg_weight=0.5)


@app.get("/health")
def health() -> dict[str, object]:
    return {"status": "ready" if model is not None else "loading", "voices": 1}


@app.get("/v1/voices")
def voices() -> dict[str, object]:
    return {
        "defaultVoiceId": "velora",
        "voices": [{"id": "velora", "name": "Velora Klar", "locale": "de-DE", "gender": "female"}],
    }


@app.post("/v1/synthesize")
def synthesize(request: SynthesisRequest) -> Response:
    if model is None:
        raise HTTPException(status_code=503, detail="TTS_LOADING")
    if request.voice_id not in {"velora", "klar"}:
        raise HTTPException(status_code=400, detail="UNKNOWN_VOICE")
    with generation_lock:
        wav = model.generate(
            request.text,
            language_id="de",
            cfg_weight=0.5,
            temperature=0.65,
            repetition_penalty=2.0,
        )
    output = io.BytesIO()
    sf.write(output, wav.squeeze(0).numpy(), model.sr, format="WAV")
    return Response(output.getvalue(), media_type="audio/wav")


def main() -> None:
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", default=8020, type=int)
    arguments = parser.parse_args()
    uvicorn.run(app, host=arguments.host, port=arguments.port)


if __name__ == "__main__":
    main()
