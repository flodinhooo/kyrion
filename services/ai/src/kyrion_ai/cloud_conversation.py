from __future__ import annotations

import asyncio
import base64
import io
import logging
import time
import uuid
import wave
from dataclasses import dataclass, field
from typing import Literal

import httpx

from kyrion_ai.config import Settings
from kyrion_ai.contracts import ChatMessage, ChatRequest
from kyrion_ai.prompts import prepare_chat_request
from kyrion_ai.speech import SpeechService

LOGGER = logging.getLogger("kyrion-ai.cloud")
Provider = Literal["gemini", "openrouter", "openrouter-explicit"]


class CloudConversationError(RuntimeError):
    pass


@dataclass(slots=True)
class CloudSession:
    id: str
    provider: Provider
    locale: str
    model: str
    touched_at: float
    history: list[dict[str, str]] = field(default_factory=list)
    gemini_context: object | None = None
    gemini_session: object | None = None


@dataclass(frozen=True, slots=True)
class CloudTurnResult:
    transcript: str
    response_text: str
    audio: bytes
    metrics: dict[str, float | int | str | None]


class CloudConversationManager:
    """Ephemeral, opt-in spike. It exposes no tools and persists no content."""

    def __init__(self, settings: Settings, speech: SpeechService) -> None:
        self.settings = settings
        self.speech = speech
        self.sessions: dict[str, CloudSession] = {}

    async def open(self, provider: Provider, locale: str) -> CloudSession:
        self._require_enabled()
        if provider == "gemini":
            if not self.settings.gemini_api_key:
                raise CloudConversationError("GEMINI_API_KEY is not configured")
            model = self.settings.gemini_live_model
        else:
            if not self.settings.openrouter_api_key:
                raise CloudConversationError("OPENROUTER_API_KEY is not configured")
            model = (
                self.settings.openrouter_explicit_free_model
                if provider == "openrouter-explicit"
                else self.settings.openrouter_model
            )
            if model != "openrouter/free" and not model.endswith(":free"):
                raise CloudConversationError("The spike only permits OpenRouter free models")
        session = CloudSession(str(uuid.uuid4()), provider, locale, model, time.monotonic())
        if provider == "gemini":
            await self._open_gemini(session)
        self.sessions[session.id] = session
        LOGGER.info(
            "cloud_session event=started id=%s provider=%s model=%s", session.id, provider, model
        )
        return session

    async def turn(self, session_id: str, wav_audio: bytes) -> CloudTurnResult:
        session = self._active(session_id)
        started = time.perf_counter()
        if session.provider == "gemini":
            result = await self._gemini_turn(session, wav_audio, started)
        else:
            result = await self._openrouter_turn(session, wav_audio, started)
        session.touched_at = time.monotonic()
        LOGGER.info(
            "cloud_turn session=%s provider=%s model=%s startup_ms=%s first_response_ms=%s "
            "first_audio_ms=%s complete_ms=%s prompt_tokens=%s completion_tokens=%s",
            session.id,
            session.provider,
            result.metrics.get("model"),
            result.metrics.get("sessionStartupMs"),
            result.metrics.get("firstResponseMs"),
            result.metrics.get("firstAudioMs"),
            result.metrics.get("completeMs"),
            result.metrics.get("promptTokens"),
            result.metrics.get("completionTokens"),
        )
        return result

    async def close(self, session_id: str, reason: str = "manual") -> None:
        session = self.sessions.pop(session_id, None)
        if session and session.gemini_context is not None:
            await session.gemini_context.__aexit__(None, None, None)  # type: ignore[attr-defined]
        if session:
            LOGGER.info(
                "cloud_session event=ended id=%s provider=%s reason=%s",
                session.id,
                session.provider,
                reason,
            )

    def _require_enabled(self) -> None:
        if not self.settings.cloud_conversation_enabled:
            raise CloudConversationError("Cloud conversations are disabled")

    def _active(self, session_id: str) -> CloudSession:
        session = self.sessions.get(session_id)
        if session is None:
            raise CloudConversationError("Cloud session not found")
        if time.monotonic() - session.touched_at > self.settings.cloud_session_timeout_seconds:
            self.sessions.pop(session_id, None)
            raise CloudConversationError("Cloud session expired")
        return session

    async def _open_gemini(self, session: CloudSession) -> None:
        try:
            from google import genai
        except ImportError as error:
            raise CloudConversationError("Install the cloud-spike optional dependency") from error
        prompt = (
            prepare_chat_request(
                ChatRequest(
                    locale=session.locale,
                    interactionMode="voice",
                    messages=[
                        ChatMessage(
                            role="user", content="Beginne die Sprachsitzung ohne Begrüßung."
                        )
                    ],
                )
            )
            .messages[0]
            .content
        )
        client = genai.Client(api_key=self.settings.gemini_api_key)
        context = client.aio.live.connect(
            model=session.model,
            config={
                "response_modalities": ["AUDIO"],
                "system_instruction": prompt,
                "input_audio_transcription": {},
                "output_audio_transcription": {},
            },
        )
        session.gemini_context = context
        session.gemini_session = await context.__aenter__()

    async def _gemini_turn(
        self, session: CloudSession, wav_audio: bytes, started: float
    ) -> CloudTurnResult:
        from google.genai import types

        pcm = _wav_pcm16_mono(wav_audio, 16_000)
        live = session.gemini_session
        await live.send_realtime_input(audio=types.Blob(data=pcm, mime_type="audio/pcm;rate=16000"))
        await live.send_realtime_input(audio_stream_end=True)
        chunks: list[bytes] = []
        input_text: list[str] = []
        output_text: list[str] = []
        first_audio_ms: float | None = None
        async for message in live.receive():
            content = message.server_content
            if content is None:
                continue
            if content.input_transcription:
                input_text.append(content.input_transcription.text or "")
            if content.output_transcription:
                output_text.append(content.output_transcription.text or "")
            if content.model_turn:
                for part in content.model_turn.parts:
                    if part.inline_data and part.inline_data.data:
                        if first_audio_ms is None:
                            first_audio_ms = (time.perf_counter() - started) * 1000
                        chunks.append(part.inline_data.data)
            if content.turn_complete:
                break
        complete = (time.perf_counter() - started) * 1000
        return CloudTurnResult(
            "".join(input_text).strip(),
            "".join(output_text).strip(),
            _pcm_to_wav(b"".join(chunks), 24_000),
            {
                "provider": "gemini",
                "model": session.model,
                "firstResponseMs": first_audio_ms,
                "firstAudioMs": first_audio_ms,
                "completeMs": complete,
                "promptTokens": None,
                "completionTokens": None,
            },
        )

    async def _openrouter_turn(
        self, session: CloudSession, wav_audio: bytes, started: float
    ) -> CloudTurnResult:
        transcript = await asyncio.to_thread(self.speech.transcribe, wav_audio, session.locale)
        session.history.append({"role": "user", "content": transcript})
        request = ChatRequest(
            locale=session.locale,
            interactionMode="voice",
            messages=[
                ChatMessage(**message)
                for message in session.history[-self.settings.cloud_history_max_messages :]
            ],
        )
        messages = [message.model_dump() for message in prepare_chat_request(request).messages]
        first_token_ms: float | None = None
        response_text = ""
        actual_model = session.model
        usage: dict[str, int] = {}
        headers = {
            "Authorization": f"Bearer {self.settings.openrouter_api_key}",
            "Content-Type": "application/json",
        }
        timeout = httpx.Timeout(120.0, connect=10.0)
        async with (
            httpx.AsyncClient(timeout=timeout) as client,
            client.stream(
                "POST",
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json={
                    "model": session.model,
                    "messages": messages,
                    "stream": True,
                    "stream_options": {"include_usage": True},
                },
            ) as response,
        ):
            if response.status_code != 200:
                raise CloudConversationError(f"OpenRouter failed with HTTP {response.status_code}")
            async for line in response.aiter_lines():
                if not line.startswith("data: ") or line == "data: [DONE]":
                    continue
                value = __import__("json").loads(line[6:])
                actual_model = value.get("model", actual_model)
                delta = value.get("choices", [{}])[0].get("delta", {}).get("content") or ""
                if delta and first_token_ms is None:
                    first_token_ms = (time.perf_counter() - started) * 1000
                response_text += delta
                usage = value.get("usage") or usage
        response_text = response_text.strip()
        session.history.append({"role": "assistant", "content": response_text})
        session.history[:] = session.history[-self.settings.cloud_history_max_messages :]
        audio = await asyncio.to_thread(self.speech.synthesize, response_text, None, session.locale)
        first_audio_ms = (time.perf_counter() - started) * 1000
        return CloudTurnResult(
            transcript,
            response_text,
            audio,
            {
                "provider": "openrouter",
                "model": actual_model,
                "firstResponseMs": first_token_ms,
                "firstAudioMs": first_audio_ms,
                "completeMs": first_audio_ms,
                "promptTokens": usage.get("prompt_tokens"),
                "completionTokens": usage.get("completion_tokens"),
            },
        )


def _wav_pcm16_mono(data: bytes, expected_rate: int) -> bytes:
    with wave.open(io.BytesIO(data), "rb") as source:
        if (
            source.getnchannels() != 1
            or source.getsampwidth() != 2
            or source.getframerate() != expected_rate
        ):
            raise CloudConversationError("Expected mono PCM16 WAV at 16 kHz")
        return source.readframes(source.getnframes())


def _pcm_to_wav(pcm: bytes, rate: int) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(rate)
        target.writeframes(pcm)
    return output.getvalue()


def encode_result(result: CloudTurnResult) -> dict[str, object]:
    return {
        "transcript": result.transcript,
        "responseText": result.response_text,
        "audioBase64": base64.b64encode(result.audio).decode("ascii"),
        "metrics": result.metrics,
    }
