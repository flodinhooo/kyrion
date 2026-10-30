"""Persistent Chatterbox TTS runtime using Velora's selected F voice."""

from __future__ import annotations

import argparse
import io
import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

import soundfile as sf
from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

REFERENCE = "/mnt/e/dev/Kyrion/kyrion/.run/velora-female-options/F_weiblich_klar.wav"
logger = logging.getLogger("kyrion.chatterbox.startup")
MODEL_FILES = [
    "ve.pt",
    "t3_mtl23ls_v2.safetensors",
    "s3gen.pt",
    "grapheme_mtl_merged_expanded_v1.json",
    "conds.pt",
    "Cangjie5_TC.json",
]


class SynthesisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4_000)
    voice_id: str = Field(alias="voiceId")


model = None
generation_lock = threading.Lock()
startup_error = None
startup_stage = "starting"


def initialize_with_retry(stop: threading.Event) -> None:
    """Bound transient local I/O retries; keep configuration failures visible."""
    global startup_error, startup_stage
    for attempt in range(3):
        if stop.is_set():
            return
        try:
            load_runtime()
            return
        except Exception as error:
            transient = isinstance(error, (OSError, TimeoutError)) and not isinstance(
                error, (FileNotFoundError, PermissionError)
            )
            if transient and attempt < 2:
                startup_stage = "retry_wait"
                logger.warning("TTS_STARTUP stage=retry attempt=%d", attempt + 1)
                if stop.wait(5 * (2**attempt)):
                    return
                continue
            startup_error = (
                "TTS_MODEL_CACHE_MISSING"
                if isinstance(error, FileNotFoundError)
                else "TTS_REFERENCE_MISSING"
                if str(error) == "TTS_REFERENCE_MISSING"
                else "TTS_INITIALIZATION_FAILED"
            )
            startup_stage = "failed"
            # Exception strings may contain private paths or provider details.
            logger.error(
                "TTS_STARTUP stage=failed code=%s type=%s", startup_error, type(error).__name__
            )
            return


@asynccontextmanager
async def lifespan(_app: FastAPI):
    stop = threading.Event()
    worker = threading.Thread(target=initialize_with_retry, args=(stop,), daemon=True)
    worker.start()
    try:
        yield
    finally:
        stop.set()


app = FastAPI(title="Kyrion Local Chatterbox TTS", version="0.1.0", lifespan=lifespan)


def load_runtime() -> None:
    global model, startup_stage
    # No network resolution/download during service startup. Provision separately.
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    started = time.monotonic()
    startup_stage = "dependencies"
    logger.warning("TTS_STARTUP stage=dependencies")
    from chatterbox.mtl_tts import REPO_ID, ChatterboxMultilingualTTS
    from huggingface_hub import snapshot_download

    reference = Path(os.environ.get("KYRION_CHATTERBOX_REFERENCE", REFERENCE))
    if not reference.is_file():
        raise RuntimeError("TTS_REFERENCE_MISSING")
    directory = os.environ.get("KYRION_CHATTERBOX_MODEL_DIRECTORY")
    if not directory:
        directory = snapshot_download(
            repo_id=REPO_ID,
            local_files_only=True,
            allow_patterns=MODEL_FILES,
        )
    logger.warning("TTS_STARTUP stage=weights elapsed_seconds=%.1f", time.monotonic() - started)
    startup_stage = "weights"
    device = os.environ.get("KYRION_CHATTERBOX_DEVICE", "cuda")
    if device not in {"cuda", "cpu"}:
        raise RuntimeError("TTS_DEVICE_INVALID")
    loaded = ChatterboxMultilingualTTS.from_local(Path(directory), device=device)
    logger.warning("TTS_STARTUP stage=reference elapsed_seconds=%.1f", time.monotonic() - started)
    startup_stage = "reference"
    loaded.prepare_conditionals(str(reference), exaggeration=0.45)
    logger.warning("TTS_STARTUP stage=warmup elapsed_seconds=%.1f", time.monotonic() - started)
    startup_stage = "warmup"
    loaded.generate("Systemstart.", language_id="de", cfg_weight=0.5)
    model = loaded  # Readiness only after every initialization step succeeded.
    startup_stage = "ready"
    logger.warning("TTS_STARTUP stage=ready elapsed_seconds=%.1f", time.monotonic() - started)


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ready" if model is not None else "error" if startup_error else "loading",
        "voices": 1,
        "stage": startup_stage,
        "code": startup_error,
    }


@app.get("/live")
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def readiness() -> JSONResponse:
    return JSONResponse(health(), status_code=200 if model is not None else 503)


@app.get("/v1/voices")
def voices() -> dict[str, object]:
    return {
        "defaultVoiceId": "velora",
        "voices": [{"id": "velora", "name": "Velora Klar", "locale": "de-DE", "gender": "female"}],
    }


@app.post("/v1/synthesize")
def synthesize(request: SynthesisRequest) -> Response:
    if model is None:
        raise HTTPException(status_code=503, detail=startup_error or "TTS_LOADING")
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
    sf.write(output, wav.squeeze(0).detach().cpu().numpy(), model.sr, format="WAV")
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
