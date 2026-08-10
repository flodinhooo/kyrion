from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import Event

SAMPLE_RATE = 24_000
CHANNELS = 1
FRAME_MILLISECONDS = 160
FRAME_BYTES = SAMPLE_RATE * CHANNELS * 2 * FRAME_MILLISECONDS // 1_000
MAX_FRAMES = 125
MAX_EVENT_BYTES = 16_384


class PcmDownlinkError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PcmDownlinkResult:
    status: str
    frames_received: int
    pcm_bytes_received: int
    first_frame_latency_millis: int | None
    maximum_frame_latency_millis: int | None


class PcmDownlinkClient:
    def __init__(
        self,
        base_url: str,
        satellite_id: str,
        credential_file: Path,
        *,
        epoch_millis: Callable[[], int] | None = None,
        urlopen: Callable[..., object] | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._satellite_id = satellite_id
        self._credential_file = credential_file
        self._epoch_millis = epoch_millis or (lambda: time.time_ns() // 1_000_000)
        self._urlopen = urlopen or urllib.request.urlopen

    def receive(
        self,
        session_id: str,
        turn_id: str,
        duration_milliseconds: int,
        consume: Callable[[bytes], None],
        *,
        clock_offset_millis: int = 0,
        cancelled: Event | None = None,
        signal: str = "silence",
    ) -> PcmDownlinkResult:
        if duration_milliseconds not in range(160, 20_001, 160):
            raise PcmDownlinkError("PCM downlink duration must use bounded 160 ms frames")
        if signal not in {"silence", "tone"}:
            raise PcmDownlinkError("PCM downlink signal is invalid")
        token = self._credential_file.read_text(encoding="utf-8").strip()
        if not token:
            raise PcmDownlinkError("Voice credential file is empty")
        request = urllib.request.Request(
            f"{self._base_url}/v1/voice-satellite/sessions/{session_id}/pcm-downlink-prototype",
            data=json.dumps({
                "turnId": turn_id,
                "durationMilliseconds": duration_milliseconds,
                "signal": signal,
            }).encode(),
            headers={
                "Authorization": f"Bearer {token}",
                "X-Kyrion-Satellite-Id": self._satellite_id,
                "Content-Type": "application/json",
                "Accept": "application/x-ndjson",
            },
            method="POST",
        )
        frames = 0
        pcm_bytes = 0
        first_latency: int | None = None
        maximum_latency: int | None = None
        started = False
        try:
            with self._urlopen(request, timeout=30) as response:
                for raw_line in response:
                    if cancelled is not None and cancelled.is_set():
                        return PcmDownlinkResult(
                            "cancelled", frames, pcm_bytes, first_latency, maximum_latency,
                        )
                    if len(raw_line) > MAX_EVENT_BYTES:
                        raise PcmDownlinkError("PCM downlink event exceeded the size limit")
                    event = json.loads(raw_line)
                    if event.get("sessionId") != session_id or event.get("turnId") != turn_id:
                        raise PcmDownlinkError("PCM downlink scope mismatch")
                    event_type = event.get("type")
                    if event_type == "start":
                        invalid_format = (
                            event.get("sampleRate") != SAMPLE_RATE
                            or event.get("channels") != CHANNELS
                        )
                        if started or invalid_format:
                            raise PcmDownlinkError("PCM downlink start was invalid")
                        if event.get("frameMilliseconds") != FRAME_MILLISECONDS:
                            raise PcmDownlinkError("PCM downlink frame duration was invalid")
                        started = True
                    elif event_type == "audio":
                        if not started or event.get("sequence") != frames or frames >= MAX_FRAMES:
                            raise PcmDownlinkError("PCM downlink sequence was invalid")
                        frame = base64.b64decode(event.get("audioBase64", ""), validate=True)
                        if len(frame) != FRAME_BYTES:
                            raise PcmDownlinkError("PCM downlink frame size was invalid")
                        produced_at = int(event["producedAtEpochMillis"])
                        latency = self._epoch_millis() + clock_offset_millis - produced_at
                        first_latency = latency if first_latency is None else first_latency
                        maximum_latency = max(maximum_latency or latency, latency)
                        consume(frame)
                        frames += 1
                        pcm_bytes += len(frame)
                    elif event_type == "complete":
                        invalid_totals = (
                            event.get("framesSent") != frames
                            or event.get("pcmBytesSent") != pcm_bytes
                        )
                        if not started or invalid_totals:
                            raise PcmDownlinkError("PCM downlink completion was invalid")
                        return PcmDownlinkResult(
                            "completed", frames, pcm_bytes, first_latency, maximum_latency,
                        )
                    else:
                        raise PcmDownlinkError("PCM downlink event type was invalid")
        except (
            OSError,
            urllib.error.URLError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ) as error:
            raise PcmDownlinkError("Core PCM downlink failed") from error
        raise PcmDownlinkError("Core PCM downlink disconnected before completion")
