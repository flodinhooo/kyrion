from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


class CoreVoiceError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class OpenSession:
    id: str
    conversation_id: str


@dataclass(frozen=True, slots=True)
class VoiceTurn:
    transcript: str
    response_text: str
    continue_session: bool


class CoreVoiceClient:
    def __init__(self, base_url: str, satellite_id: str, credential_file: Path) -> None:
        self._base_url = base_url.rstrip("/")
        self._satellite_id = satellite_id
        self._credential_file = credential_file

    def open_session(self) -> OpenSession:
        value = self._request("POST", "/v1/voice-satellite/sessions", b"", "application/json")
        return OpenSession(value["sessionId"], value["conversationId"])

    def turn(
        self,
        session_id: str,
        wav: bytes,
        locale: str,
        play_audio: Callable[[bytes], None],
        turn_id: str,
    ) -> VoiceTurn:
        request = self._build_request(
            "POST",
            f"/v1/voice-satellite/sessions/{session_id}/turns",
            wav,
            "audio/wav",
            {
                "X-Kyrion-Locale": locale,
                "X-Kyrion-Voice-Turn-Id": turn_id,
                "Accept": "application/x-ndjson",
            },
        )
        transcript = ""
        response_text = ""
        continue_session = False
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                for raw_line in response:
                    if not raw_line.strip():
                        continue
                    event = json.loads(raw_line)
                    event_type = event.get("type")
                    if event_type == "transcript":
                        transcript = event.get("transcript", "")
                    elif event_type == "audio.chunk":
                        play_audio(base64.b64decode(event["audioBase64"], validate=True))
                    elif event_type == "completed":
                        response_text = event.get("responseText", "")
                        continue_session = bool(event.get("continueSession"))
        except (
            urllib.error.HTTPError,
            urllib.error.URLError,
            TimeoutError,
            ValueError,
            KeyError,
        ) as error:
            raise CoreVoiceError("Core voice stream failed") from error
        if not transcript or not response_text:
            raise CoreVoiceError("Core voice stream ended before completion")
        return VoiceTurn(transcript, response_text, continue_session)

    def close_session(self, session_id: str, reason: str) -> None:
        self._request(
            "POST",
            "/v1/voice-satellite/sessions/close",
            json.dumps({"sessionId": session_id, "reason": reason}).encode(),
            "application/json",
        )

    def _request(
        self,
        method: str,
        path: str,
        body: bytes,
        content_type: str,
        extra_headers: dict[str, str] | None = None,
    ) -> dict:
        request = self._build_request(method, path, body, content_type, extra_headers)
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                payload = response.read()
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
            raise CoreVoiceError("Core voice request failed") from error
        if not payload:
            return {}
        try:
            value = json.loads(payload)
        except json.JSONDecodeError as error:
            raise CoreVoiceError("Core returned invalid JSON") from error
        if not isinstance(value, dict):
            raise CoreVoiceError("Core returned an invalid response")
        return value

    def _build_request(
        self,
        method: str,
        path: str,
        body: bytes,
        content_type: str,
        extra_headers: dict[str, str] | None = None,
    ) -> urllib.request.Request:
        token = self._credential_file.read_text(encoding="utf-8").strip()
        if not token:
            raise CoreVoiceError("Voice credential file is empty")
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Kyrion-Satellite-Id": self._satellite_id,
            "Content-Type": content_type,
            **(extra_headers or {}),
        }
        return urllib.request.Request(
            f"{self._base_url}{path}", data=body, headers=headers, method=method,
        )
