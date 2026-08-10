"""Isolated experimental XTTS-v2 streaming runtime for the Velora MVP voice."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import logging
import os
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import UUID

import numpy as np
import torch
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from TTS.api import TTS

ROOT = Path("/mnt/e/dev/Kyrion/kyrion")
REFERENCE = ROOT / ".run/velora-female-options/F_weiblich_klar.wav"
REFERENCE_SHA256 = "d2afdc5faa3fb6cc41756daaaac3db63c30679e3bcd3e87f6dab0055d08dad09"
SAMPLE_RATE = 24_000
STREAM_CHUNK_TOKENS = 20
OVERLAP_WAV_SAMPLES = 1_024

logger = logging.getLogger("kyrion-xtts-v2-experimental")
app = FastAPI(title="Kyrion Experimental XTTS-v2 Streaming TTS", version="0.1.0")
model: Any | None = None
conditioning: tuple[torch.Tensor, torch.Tensor] | None = None
generation_lock = threading.Lock()


class SynthesisRequest(BaseModel):
    turn_id: UUID = Field(alias="turnId")
    text: str = Field(min_length=1, max_length=500)
    locale: str = Field(pattern="^(de|en)$")
    voice_profile_id: str = Field(alias="voiceProfileId", pattern="^(velora|velora-f|klar)$")
    phrase_index: int = Field(alias="phraseIndex", ge=0)
    final_phrase: bool = Field(alias="finalPhrase")


@app.on_event("startup")
def load_runtime() -> None:
    global model, conditioning
    if hashlib.sha256(REFERENCE.read_bytes()).hexdigest() != REFERENCE_SHA256:
        raise RuntimeError("Velora F reference checksum mismatch")
    runtime = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cuda")
    model = runtime.synthesizer.tts_model
    conditioning = model.get_conditioning_latents(audio_path=[str(REFERENCE)])
    list(_inference_stream("Systemstart.", "de"))


def _inference_stream(text: str, locale: str) -> Iterator[torch.Tensor]:
    assert model is not None and conditioning is not None
    unstable_cap_enabled = os.getenv("KYRION_XTTS_UNSTABLE_LENGTH_CAP_ENABLED", "true").lower() in {
        "1",
        "true",
        "yes",
    }
    original_limit = model.gpt.max_gen_mel_tokens
    if unstable_cap_enabled:
        # Unstable MVP workaround: this private XTTS field is adapter-local and must not
        # become part of Kyrion's TTS contract. Remove it once public termination is stable.
        model.gpt.max_gen_mel_tokens = max(48, 14 * len(text.split()))
    try:
        yield from model.inference_stream(
            text,
            locale,
            *conditioning,
            stream_chunk_size=STREAM_CHUNK_TOKENS,
            overlap_wav_len=OVERLAP_WAV_SAMPLES,
            do_sample=True,
            temperature=0.75,
            top_k=50,
            top_p=0.85,
            repetition_penalty=10.0,
        )
    finally:
        model.gpt.max_gen_mel_tokens = original_limit


@app.get("/health")
def health() -> dict[str, object]:
    return {"status": "ready" if model is not None else "loading", "experimental": True}


@app.get("/v1/streaming/capabilities")
def capabilities() -> dict[str, object]:
    return {
        "providerId": "xtts-v2-experimental",
        "incrementalOutput": True,
        "cancellation": True,
        "voiceCloning": True,
        "sampleFormat": "pcm_s16le",
        "sampleRate": SAMPLE_RATE,
        "channels": 1,
        "minimumTextGranularity": "phrase",
        "maximumTextCharacters": 500,
        "maximumChunkMilliseconds": 2_000,
        "cancellationDeadlineMilliseconds": 250,
    }


@app.post("/v1/synthesize/stream")
def synthesize_stream(request: SynthesisRequest) -> StreamingResponse:
    if model is None:
        raise HTTPException(status_code=503, detail="TTS_LOADING")

    def events() -> Iterator[bytes]:
        sequence = 0
        try:
            with generation_lock:
                for tensor in _inference_stream(request.text, request.locale):
                    audio = tensor.detach().float().cpu().numpy()
                    pcm = (np.clip(audio, -1.0, 1.0) * 32_767).astype("<i2").tobytes()
                    event = {
                        "type": "audio",
                        "sequence": sequence,
                        "audioBase64": base64.b64encode(pcm).decode("ascii"),
                        "producedAtEpochMillis": time.time_ns() // 1_000_000,
                    }
                    sequence += 1
                    yield json.dumps(event, separators=(",", ":")).encode() + b"\n"
            yield json.dumps({"type": "complete", "chunks": sequence}).encode() + b"\n"
        except GeneratorExit:
            logger.info("XTTS stream cancelled turn=%s chunks=%d", request.turn_id, sequence)
            raise
        except Exception:
            logger.exception("XTTS generation failed turn=%s", request.turn_id)
            yield b'{"type":"error","code":"TTS_PROVIDER_FAILURE"}\n'

    return StreamingResponse(
        events(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


def main() -> None:
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8031, type=int)
    arguments = parser.parse_args()
    uvicorn.run(app, host=arguments.host, port=arguments.port)


if __name__ == "__main__":
    main()
