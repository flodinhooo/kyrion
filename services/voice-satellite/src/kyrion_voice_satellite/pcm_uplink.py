from __future__ import annotations

import base64
import http.client
import json
import time
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from urllib.parse import urlsplit

from kyrion_voice_satellite.audio import FRAME_BYTES, SAMPLE_RATE

CHANNELS = 1
MAX_FRAMES = 750  # 60 seconds at the satellite's fixed 80 ms capture frame.


class PcmUplinkError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PcmUplinkResult:
    status: str
    frames_received: int
    pcm_bytes_received: int
    first_frame_latency_millis: int | None
    maximum_frame_latency_millis: int | None


class PcmUplinkClient:
    def __init__(
        self,
        base_url: str,
        satellite_id: str,
        credential_file: Path,
        *,
        connection_factory: Callable[..., http.client.HTTPConnection] | None = None,
        epoch_millis: Callable[[], int] | None = None,
    ) -> None:
        target = urlsplit(base_url)
        if target.scheme not in {"http", "https"} or not target.hostname:
            raise ValueError("Core URL must use HTTP or HTTPS")
        self._target = target
        self._satellite_id = satellite_id
        self._credential_file = credential_file
        self._connection_factory = connection_factory
        self._epoch_millis = epoch_millis or (lambda: time.time_ns() // 1_000_000)

    def stream(
        self,
        session_id: str,
        turn_id: str,
        frames: Iterable[bytes],
        *,
        cancelled: Event | None = None,
    ) -> PcmUplinkResult:
        token = self._credential_file.read_text(encoding="utf-8").strip()
        if not token:
            raise PcmUplinkError("Voice credential file is empty")
        connection = self._connection()
        path_prefix = self._target.path.rstrip("/")
        path = f"{path_prefix}/v1/voice-satellite/sessions/{session_id}/pcm-uplink"
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Kyrion-Satellite-Id": self._satellite_id,
            "X-Kyrion-Voice-Turn-Id": turn_id,
            "Content-Type": "application/x-ndjson",
            "Accept": "application/json",
        }
        try:
            connection.request(
                "POST",
                path,
                body=self._events(session_id, turn_id, frames, cancelled),
                headers=headers,
                encode_chunked=True,
            )
            response = connection.getresponse()
            payload = response.read()
        except (OSError, http.client.HTTPException, ValueError) as error:
            raise PcmUplinkError("Core PCM uplink failed") from error
        finally:
            connection.close()
        if response.status < 200 or response.status >= 300:
            raise PcmUplinkError(f"Core PCM uplink rejected with HTTP {response.status}")
        try:
            value = json.loads(payload)
            return PcmUplinkResult(
                status=value["status"],
                frames_received=int(value["framesReceived"]),
                pcm_bytes_received=int(value["pcmBytesReceived"]),
                first_frame_latency_millis=value.get("firstFrameLatencyMillis"),
                maximum_frame_latency_millis=value.get("maximumFrameLatencyMillis"),
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            raise PcmUplinkError("Core returned an invalid PCM uplink response") from error

    def _events(
        self,
        session_id: str,
        turn_id: str,
        frames: Iterable[bytes],
        cancelled: Event | None,
    ) -> Iterator[bytes]:
        scope = {"sessionId": session_id, "turnId": turn_id}
        yield self._line(
            {"type": "start", **scope, "sampleRate": SAMPLE_RATE, "channels": CHANNELS}
        )
        for sequence, frame in enumerate(frames):
            if cancelled is not None and cancelled.is_set():
                yield self._line({"type": "cancel", **scope, "reason": "interrupted"})
                return
            if sequence >= MAX_FRAMES:
                raise PcmUplinkError("PCM uplink exceeded the 60 second frame limit")
            if len(frame) != FRAME_BYTES:
                raise PcmUplinkError("Capture returned an invalid PCM frame")
            yield self._line(
                {
                    "type": "audio",
                    **scope,
                    "sampleRate": SAMPLE_RATE,
                    "channels": CHANNELS,
                    "sequence": sequence,
                    "capturedAtEpochMillis": self._epoch_millis(),
                    "audioBase64": base64.b64encode(frame).decode("ascii"),
                }
            )
        terminal = "cancel" if cancelled is not None and cancelled.is_set() else "complete"
        yield self._line({"type": terminal, **scope})

    @staticmethod
    def _line(value: dict[str, object]) -> bytes:
        return json.dumps(value, separators=(",", ":")).encode("utf-8") + b"\n"

    def _connection(self) -> http.client.HTTPConnection:
        port = self._target.port
        factory = self._connection_factory
        if factory is not None:
            return factory(self._target.hostname, port, timeout=90)
        connection_type = (
            http.client.HTTPSConnection
            if self._target.scheme == "https"
            else http.client.HTTPConnection
        )
        return connection_type(self._target.hostname, port, timeout=90)
