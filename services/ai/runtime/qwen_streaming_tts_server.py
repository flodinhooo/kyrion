"""Isolated capability-reporting Qwen3-TTS streaming runtime."""

from __future__ import annotations

import argparse
import asyncio
import base64
import contextlib
import functools
import hashlib
import json
import logging
import queue
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

import numpy as np
import torch
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from qwen_tts import Qwen3TTSModel

ROOT = Path("/mnt/e/dev/Kyrion/kyrion")
MODEL_PATH = "/training/models/qwen3-tts/voice-clone-base"
REFERENCE = ROOT / ".run/velora-female-options/F_weiblich_klar.wav"
REFERENCE_SHA256 = "d2afdc5faa3fb6cc41756daaaac3db63c30679e3bcd3e87f6dab0055d08dad09"
TRANSCRIPT = (
    "Guten Morgen. Ich bin Velora. Für heute stehen noch zwei Aufgaben auf deiner Liste. "
    "Möchtest du zuerst den Überblick hören, oder sollen wir direkt anfangen?"
)
SAMPLE_RATE = 24_000
SAMPLES_PER_CODEC_FRAME = 1_920
INITIAL_CODEC_FRAMES = 10
STRIDE_CODEC_FRAMES = 20
CONTEXT_CODEC_FRAMES = 50
MAX_STREAM_EVENTS = 4

logger = logging.getLogger("kyrion-qwen-streaming-tts")
app = FastAPI(title="Kyrion Isolated Qwen Streaming TTS", version="0.1.0")
runtime: Qwen3TTSModel | None = None
prompt_items: list[Any] | None = None
generation_lock = threading.Lock()
active_turns: dict[UUID, threading.Event] = {}
active_turns_lock = threading.Lock()


class GenerationCancelled(RuntimeError):
    pass


class SynthesisRequest(BaseModel):
    turn_id: UUID = Field(alias="turnId")
    text: str = Field(min_length=1, max_length=500)
    locale: str = Field(pattern="^(de|en)$")
    voice_profile_id: str = Field(alias="voiceProfileId", pattern="^velora-f$")
    phrase_index: int = Field(alias="phraseIndex", ge=0)
    final_phrase: bool = Field(alias="finalPhrase")


def install_frame_hook(
    talker: Any,
    on_frame: Callable[[int, torch.Tensor], None],
    cancelled: threading.Event,
) -> Callable[[], None]:
    original = talker.forward
    frame_index = 0

    @functools.wraps(original)
    def hooked(*args: Any, **kwargs: Any) -> Any:
        nonlocal frame_index
        if cancelled.is_set():
            raise GenerationCancelled
        output = original(*args, **kwargs)
        codec_ids = output.hidden_states[1] if output.hidden_states else None
        if codec_ids is not None:
            frame = codec_ids[0].detach().clone()
            if frame.numel() != 16:
                raise RuntimeError("Qwen returned an invalid codec frame")
            on_frame(frame_index, frame)
            frame_index += 1
        if cancelled.is_set():
            raise GenerationCancelled
        return output

    talker.forward = hooked

    def restore() -> None:
        talker.forward = original

    return restore


def prepare_generation(text: str, locale: str) -> tuple[dict[str, Any], torch.Tensor]:
    if runtime is None or prompt_items is None:
        raise RuntimeError("Qwen runtime is unavailable")
    prompt = runtime._prompt_items_to_voice_clone_prompt(prompt_items)
    input_ids = runtime._tokenize_texts([runtime._build_assistant_text(text)])
    ref_text = prompt_items[0].ref_text
    ref_ids = [runtime._tokenize_texts([runtime._build_ref_text(ref_text)])[0]]
    kwargs = runtime._merge_generate_kwargs(
        do_sample=True,
        temperature=0.9,
        top_k=50,
        top_p=1.0,
        repetition_penalty=1.05,
        subtalker_dosample=True,
        subtalker_temperature=0.9,
        subtalker_top_k=50,
        subtalker_top_p=1.0,
        max_new_tokens=2_048,
    )
    return (
        {
            "input_ids": input_ids,
            "ref_ids": ref_ids,
            "voice_clone_prompt": prompt,
            "languages": ["German" if locale == "de" else "English"],
            "non_streaming_mode": False,
            **kwargs,
        },
        prompt["ref_code"][0],
    )


def decode_codes(codes: torch.Tensor) -> np.ndarray:
    assert runtime is not None
    wavs, _ = runtime.model.speech_tokenizer.decode([{"audio_codes": codes}])
    return wavs[0]


def pcm_s16le(audio: np.ndarray) -> bytes:
    return (np.clip(audio, -1.0, 1.0) * 32_767).astype("<i2").tobytes()


@dataclass
class PcmEmitter:
    reference_codes: torch.Tensor
    cancelled: threading.Event
    events: queue.Queue[dict[str, object]]
    frames: list[torch.Tensor] = field(default_factory=list)
    decoded_until: int = 0
    sequence: int = 0
    pcm_bytes: int = 0

    def on_frame(self, _index: int, frame: torch.Tensor) -> None:
        if self.cancelled.is_set():
            raise GenerationCancelled
        self.frames.append(frame)
        count = len(self.frames)
        initial_batch_ready = self.decoded_until == 0 and count == INITIAL_CODEC_FRAMES
        stride_ready = (
            self.decoded_until > 0
            and count - self.decoded_until == STRIDE_CODEC_FRAMES
        )
        if initial_batch_ready or stride_ready:
            self.decode(count)

    def decode(self, end: int) -> None:
        if self.cancelled.is_set():
            raise GenerationCancelled
        first = self.decoded_until == 0
        new_count = end if first else end - self.decoded_until
        context_start = max(0, self.decoded_until - CONTEXT_CODEC_FRAMES)
        generated = torch.stack(self.frames[context_start:end])
        if first:
            reference = self.reference_codes[-CONTEXT_CODEC_FRAMES:].to(generated.device)
            context_frames = len(reference)
            codes = torch.cat([reference, generated])
        else:
            context_frames = self.decoded_until - context_start
            codes = generated
        torch.cuda.synchronize()
        wav = decode_codes(codes)
        torch.cuda.synchronize()
        cut = context_frames * SAMPLES_PER_CODEC_FRAME
        audio = wav[cut : cut + new_count * SAMPLES_PER_CODEC_FRAME]
        payload = pcm_s16le(audio)
        self.put({
            "type": "audio",
            "sequence": self.sequence,
            "audioBase64": base64.b64encode(payload).decode("ascii"),
            "producedAtEpochMillis": time.time_ns() // 1_000_000,
        })
        self.sequence += 1
        self.pcm_bytes += len(payload)
        self.decoded_until = end

    def finish(self) -> None:
        if len(self.frames) > self.decoded_until and not self.cancelled.is_set():
            self.decode(len(self.frames))

    def put(self, event: dict[str, object]) -> None:
        while not self.cancelled.is_set():
            try:
                self.events.put(event, timeout=0.1)
                return
            except queue.Full:
                continue
        raise GenerationCancelled


def generate(request: SynthesisRequest, cancelled: threading.Event, events: queue.Queue) -> None:
    terminal_event: dict[str, object]
    try:
        with generation_lock:
            if cancelled.is_set():
                raise GenerationCancelled
            generation, reference_codes = prepare_generation(request.text, request.locale)
            emitter = PcmEmitter(reference_codes, cancelled, events)
            assert runtime is not None
            restore = install_frame_hook(runtime.model.talker, emitter.on_frame, cancelled)
            try:
                runtime.model.generate(**generation)
                emitter.finish()
            finally:
                restore()
            terminal_event = {
                "type": "complete",
                "chunks": emitter.sequence,
                "pcmBytes": emitter.pcm_bytes,
            }
    except GenerationCancelled:
        terminal_event = {"type": "cancelled"}
    except Exception:
        logger.exception("Qwen streaming generation failed for turn %s", request.turn_id)
        terminal_event = {"type": "error", "code": "TTS_PROVIDER_FAILURE"}
    finally:
        with active_turns_lock:
            active_turns.pop(request.turn_id, None)
    terminal_deadline = time.monotonic() + 2
    while time.monotonic() < terminal_deadline:
        try:
            events.put(terminal_event, timeout=0.1)
            return
        except queue.Full:
            continue
    logger.warning("Dropping terminal event for disconnected turn %s", request.turn_id)


@app.on_event("startup")
def load_runtime() -> None:
    global runtime, prompt_items
    if hashlib.sha256(REFERENCE.read_bytes()).hexdigest() != REFERENCE_SHA256:
        raise RuntimeError("Velora F reference checksum mismatch")
    runtime = Qwen3TTSModel.from_pretrained(
        MODEL_PATH,
        device_map="cuda:0",
        dtype=torch.float16,
        attn_implementation="sdpa",
    )
    prompt_items = runtime.create_voice_clone_prompt(
        ref_audio=str(REFERENCE), ref_text=TRANSCRIPT, x_vector_only_mode=False
    )
    prompt = runtime._prompt_items_to_voice_clone_prompt(prompt_items)
    decode_codes(prompt["ref_code"][0][-CONTEXT_CODEC_FRAMES:])
    runtime.generate_voice_clone(
        text="Systemstart.",
        language="German",
        voice_clone_prompt=prompt_items,
        do_sample=True,
        temperature=0.9,
        top_k=50,
        top_p=1.0,
        repetition_penalty=1.05,
        subtalker_dosample=True,
        subtalker_temperature=0.9,
        subtalker_top_k=50,
        subtalker_top_p=1.0,
        max_new_tokens=256,
    )
    torch.cuda.synchronize()


@app.get("/health")
def health() -> dict[str, object]:
    return {"status": "ready" if runtime is not None else "loading", "voices": 1}


@app.get("/v1/streaming/capabilities")
def capabilities() -> dict[str, object]:
    return {
        "providerId": "qwen3-tts-1.7b",
        "incrementalOutput": True,
        "cancellation": True,
        "voiceCloning": True,
        "sampleFormat": "pcm_s16le",
        "sampleRate": SAMPLE_RATE,
        "channels": 1,
        "minimumTextGranularity": "phrase",
        "maximumTextCharacters": 500,
        "maximumChunkMilliseconds": 1_600,
        "cancellationDeadlineMilliseconds": 250,
    }


@app.post("/v1/synthesize/{turn_id}/cancel", status_code=204)
def cancel(turn_id: UUID) -> Response:
    with active_turns_lock:
        cancelled = active_turns.get(turn_id)
    if cancelled is None:
        raise HTTPException(status_code=404, detail="TURN_NOT_ACTIVE")
    cancelled.set()
    return Response(status_code=204)


@app.post("/v1/synthesize/stream")
async def synthesize_stream(request: SynthesisRequest, http_request: Request) -> Response:
    if runtime is None:
        raise HTTPException(status_code=503, detail="TTS_LOADING")
    cancelled = threading.Event()
    with active_turns_lock:
        if request.turn_id in active_turns:
            raise HTTPException(status_code=409, detail="TURN_ALREADY_ACTIVE")
        active_turns[request.turn_id] = cancelled
    events: queue.Queue[dict[str, object]] = queue.Queue(maxsize=MAX_STREAM_EVENTS)
    worker = threading.Thread(target=generate, args=(request, cancelled, events), daemon=True)
    worker.start()

    async def watch_disconnect() -> None:
        while worker.is_alive() and not cancelled.is_set():
            if await http_request.is_disconnected():
                cancelled.set()
                return
            await asyncio.sleep(0.05)

    async def stream():
        watcher = asyncio.create_task(watch_disconnect())
        try:
            while True:
                event = await asyncio.to_thread(events.get)
                yield json.dumps(event, separators=(",", ":")).encode() + b"\n"
                if event["type"] in {"complete", "cancelled", "error"}:
                    return
        finally:
            cancelled.set()
            watcher.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await watcher
            await asyncio.to_thread(worker.join, 2)

    return StreamingResponse(
        stream(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


def main() -> None:
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8030, type=int)
    arguments = parser.parse_args()
    uvicorn.run(app, host=arguments.host, port=arguments.port)


if __name__ == "__main__":
    main()
