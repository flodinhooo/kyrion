from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from kyrion_ai.contracts import (
    DynamicVoiceResponsePlan,
    FixedVoiceResponsePlan,
    TemplateVoiceResponsePlan,
    VoiceResponsePlan,
)

logger = logging.getLogger("uvicorn.error.kyrion-ai.voice-responses")


class VoiceResponseResolutionError(RuntimeError):
    pass


class NormalTtsFallback(Protocol):
    def synthesize(self, text: str, voice_id: str | None = None, locale: str = "de") -> bytes: ...


@dataclass(frozen=True, slots=True)
class ResolvedVoiceAudio:
    audio: bytes
    source: str
    cache_hit: bool
    fallback_reason: str | None = None


class FixedAudioManifest:
    def __init__(self, manifest_path: Path) -> None:
        self._manifest_path = manifest_path.resolve()
        self._asset_root = self._manifest_path.parent.resolve()
        try:
            payload = json.loads(self._manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise VoiceResponseResolutionError("VOICE_RESPONSE_MANIFEST_INVALID") from error
        if payload.get("schemaVersion") != 1:
            raise VoiceResponseResolutionError("VOICE_RESPONSE_MANIFEST_INVALID")
        self.catalog_revision = payload.get("catalogRevision")
        self.pending_assets = tuple(payload.get("pendingAssets", ()))
        self._assets = {
            self._key(item): item
            for item in payload.get("assets", ())
            if isinstance(item, dict)
        }

    def resolve(self, plan: FixedVoiceResponsePlan) -> bytes | None:
        item = self._assets.get(
            (
                plan.catalog_revision,
                plan.voice_profile_id,
                plan.voice_profile_revision,
                plan.locale,
                plan.response_key,
                plan.variant_id,
            )
        )
        if item is None:
            return None
        relative_path = item.get("path")
        expected_sha256 = item.get("sha256")
        if not isinstance(relative_path, str) or not isinstance(expected_sha256, str):
            raise VoiceResponseResolutionError("VOICE_RESPONSE_ASSET_INVALID")
        asset = (self._asset_root / relative_path).resolve()
        if self._asset_root not in asset.parents or not asset.is_file():
            raise VoiceResponseResolutionError("VOICE_RESPONSE_ASSET_INVALID")
        audio = asset.read_bytes()
        if not audio.startswith(b"RIFF") or hashlib.sha256(audio).hexdigest() != expected_sha256:
            raise VoiceResponseResolutionError("VOICE_RESPONSE_ASSET_INVALID")
        return audio

    @staticmethod
    def _key(item: dict[str, object]) -> tuple[object, ...]:
        return (
            item.get("catalogRevision"),
            item.get("voiceProfileId"),
            item.get("voiceProfileRevision"),
            item.get("locale"),
            item.get("responseKey"),
            item.get("variantId"),
        )


class CompleteUtteranceAudioCache:
    def __init__(self, root: Path, synthesis_revision: str) -> None:
        self._root = root
        self._synthesis_revision = synthesis_revision

    def key(self, plan: TemplateVoiceResponsePlan) -> str:
        identity = {
            "catalogRevision": plan.catalog_revision,
            "templateKey": plan.template_key,
            "slots": {
                name: slot.model_dump(mode="json") for name, slot in sorted(plan.slots.items())
            },
            "renderedText": plan.rendered_text,
            "locale": plan.locale,
            "voiceProfileId": plan.voice_profile_id,
            "voiceProfileRevision": plan.voice_profile_revision,
            "synthesisRevision": self._synthesis_revision,
            "audioFormat": "wav",
        }
        canonical = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()

    def get(self, plan: TemplateVoiceResponsePlan) -> bytes | None:
        path = self._root / f"{self.key(plan)}.wav"
        try:
            audio = path.read_bytes()
        except FileNotFoundError:
            return None
        if not audio.startswith(b"RIFF"):
            logger.warning("Ignoring invalid voice-response cache entry key=%s", path.stem)
            return None
        return audio

    def put(self, plan: TemplateVoiceResponsePlan, audio: bytes) -> None:
        if not audio.startswith(b"RIFF"):
            raise VoiceResponseResolutionError("VOICE_RESPONSE_AUDIO_INVALID")
        self._root.mkdir(parents=True, exist_ok=True)
        target = self._root / f"{self.key(plan)}.wav"
        temporary = target.with_suffix(".tmp")
        temporary.write_bytes(audio)
        temporary.replace(target)


class VoiceResponseAudioResolver:
    def __init__(
        self,
        manifest: FixedAudioManifest,
        cache: CompleteUtteranceAudioCache,
        normal_tts: NormalTtsFallback,
    ) -> None:
        self._manifest = manifest
        self._cache = cache
        self._normal_tts = normal_tts

    def resolve(self, plan: VoiceResponsePlan) -> ResolvedVoiceAudio:
        if isinstance(plan, FixedVoiceResponsePlan):
            return self._resolve_fixed(plan)
        if isinstance(plan, TemplateVoiceResponsePlan):
            return self._resolve_template(plan)
        if isinstance(plan, DynamicVoiceResponsePlan):
            return ResolvedVoiceAudio(
                self._synthesize(plan), "normal_tts", False, None
            )
        raise VoiceResponseResolutionError("VOICE_RESPONSE_PLAN_UNSUPPORTED")

    def _resolve_fixed(self, plan: FixedVoiceResponsePlan) -> ResolvedVoiceAudio:
        audio = self._manifest.resolve(plan)
        if audio is not None:
            return ResolvedVoiceAudio(audio, "prerendered", True, None)
        return ResolvedVoiceAudio(
            self._synthesize(plan),
            "normal_tts",
            False,
            "fixed_asset_pending_review",
        )

    def _resolve_template(self, plan: TemplateVoiceResponsePlan) -> ResolvedVoiceAudio:
        audio = self._cache.get(plan)
        if audio is not None:
            return ResolvedVoiceAudio(audio, "template_cache", True, None)
        audio = self._synthesize(plan)
        self._cache.put(plan, audio)
        return ResolvedVoiceAudio(audio, "normal_tts", False, "template_cache_miss")

    def _synthesize(self, plan: VoiceResponsePlan) -> bytes:
        audio = self._normal_tts.synthesize(
            plan.rendered_text, plan.voice_profile_id, plan.locale
        )
        if not audio.startswith(b"RIFF"):
            raise VoiceResponseResolutionError("VOICE_RESPONSE_AUDIO_INVALID")
        return audio

