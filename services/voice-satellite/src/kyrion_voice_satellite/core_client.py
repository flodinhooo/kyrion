from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
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
    audio: bytes
    continue_session: bool


class CoreVoiceClient:
    def __init__(self, base_url: str, satellite_id: str, credential_file: Path) -> None:
        self._base_url = base_url.rstrip("/")
        self._satellite_id = satellite_id
        self._credential_file = credential_file

    def open_session(self) -> OpenSession:
        value = self._request("POST", "/v1/voice-satellite/sessions", b"", "application/json")
        return OpenSession(value["sessionId"], value["conversationId"])

    def turn(self, session_id: str, wav: bytes, locale: str) -> VoiceTurn:
        value = self._request(
            "POST",
            f"/v1/voice-satellite/sessions/{session_id}/turns",
            wav,
            "audio/wav",
            {"X-Kyrion-Locale": locale},
        )
        return VoiceTurn(
            value["transcript"], value["responseText"],
            base64.b64decode(value["audioBase64"], validate=True), value["continueSession"],
        )

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
        token = self._credential_file.read_text(encoding="utf-8").strip()
        if not token:
            raise CoreVoiceError("Voice credential file is empty")
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Kyrion-Satellite-Id": self._satellite_id,
            "Content-Type": content_type,
            **(extra_headers or {}),
        }
        request = urllib.request.Request(
            f"{self._base_url}{path}", data=body, headers=headers, method=method,
        )
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
