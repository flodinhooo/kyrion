import json
from dataclasses import replace
from pathlib import Path

import pytest

from kyrion_ai.contracts import (
    DynamicVoiceResponsePlan,
    FixedVoiceResponsePlan,
    TemplateVoiceResponsePlan,
    VoiceResponseSlot,
)
from kyrion_ai.voice_responses import (
    CompleteUtteranceAudioCache,
    FixedAudioManifest,
    VoiceResponseAudioResolver,
)

WAV = b"RIFF" + b"\x00" * 40
VOICE_REVISION = "d2afdc5faa3fb6cc41756daaaac3db63c30679e3bcd3e87f6dab0055d08dad09"


class RecordingTts:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None, str]] = []

    def synthesize(self, text: str, voice_id: str | None = None, locale: str = "de") -> bytes:
        self.calls.append((text, voice_id, locale))
        return WAV


def write_manifest(path: Path, assets: list[dict] | None = None) -> None:
    path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "catalogRevision": "voice-responses-v1",
                "assets": assets or [],
                "pendingAssets": [],
            }
        ),
        encoding="utf-8",
    )


def fixed_plan() -> FixedVoiceResponsePlan:
    return FixedVoiceResponsePlan.model_validate(
        {
            "kind": "fixed",
            "responseType": "session.farewell",
            "responseKey": "session.farewell",
            "variantId": "neutral-01",
            "locale": "de",
            "voiceProfileId": "velora",
            "voiceProfileRevision": VOICE_REVISION,
            "catalogRevision": "voice-responses-v1",
            "renderedText": "Bis später.",
        }
    )


def template_plan(**updates: object) -> TemplateVoiceResponsePlan:
    values = {
        "kind": "template",
        "responseType": "command.succeeded",
        "templateKey": "command.succeeded",
        "slots": {"targetName": {"type": "entityName", "value": "Gamingraum"}},
        "locale": "de",
        "voiceProfileId": "velora",
        "voiceProfileRevision": VOICE_REVISION,
        "catalogRevision": "voice-responses-v1",
        "renderedText": "Gamingraum wurde erfolgreich aktualisiert.",
        **updates,
    }
    return TemplateVoiceResponsePlan.model_validate(values)


def resolver(tmp_path: Path, tts: RecordingTts) -> VoiceResponseAudioResolver:
    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path)
    return VoiceResponseAudioResolver(
        FixedAudioManifest(manifest_path),
        CompleteUtteranceAudioCache(tmp_path / "cache", "normal-v1"),
        tts,
    )


def test_fixed_response_uses_normal_provider_while_reviewed_asset_is_pending(tmp_path: Path) -> None:
    tts = RecordingTts()

    result = resolver(tmp_path, tts).resolve(fixed_plan())

    assert result.source == "normal_tts"
    assert result.fallback_reason == "fixed_asset_pending_review"
    assert tts.calls == [("Bis später.", "velora", "de")]


def test_fixed_response_reads_checksum_pinned_reviewed_asset(tmp_path: Path) -> None:
    import hashlib

    asset = tmp_path / "farewell.wav"
    asset.write_bytes(WAV)
    manifest_path = tmp_path / "manifest.json"
    plan = fixed_plan()
    write_manifest(
        manifest_path,
        [
            {
                "catalogRevision": plan.catalog_revision,
                "voiceProfileId": plan.voice_profile_id,
                "voiceProfileRevision": plan.voice_profile_revision,
                "locale": plan.locale,
                "responseKey": plan.response_key,
                "variantId": plan.variant_id,
                "path": asset.name,
                "sha256": hashlib.sha256(WAV).hexdigest(),
            }
        ],
    )
    tts = RecordingTts()
    audio = VoiceResponseAudioResolver(
        FixedAudioManifest(manifest_path),
        CompleteUtteranceAudioCache(tmp_path / "cache", "normal-v1"),
        tts,
    ).resolve(plan)

    assert audio.source == "prerendered"
    assert audio.audio == WAV
    assert tts.calls == []


def test_template_response_caches_complete_utterance(tmp_path: Path) -> None:
    tts = RecordingTts()
    audio_resolver = resolver(tmp_path, tts)
    plan = template_plan()

    first = audio_resolver.resolve(plan)
    second = audio_resolver.resolve(plan)

    assert first.cache_hit is False
    assert second.cache_hit is True
    assert second.source == "template_cache"
    assert len(tts.calls) == 1


@pytest.mark.parametrize(
    "updates",
    [
        {"catalogRevision": "voice-responses-v2"},
        {"voiceProfileRevision": "velora-revision-2"},
    ],
)
def test_catalog_or_voice_revision_invalidates_template_cache(
    tmp_path: Path, updates: dict[str, str]
) -> None:
    tts = RecordingTts()
    audio_resolver = resolver(tmp_path, tts)

    audio_resolver.resolve(template_plan())
    audio_resolver.resolve(template_plan(**updates))

    assert len(tts.calls) == 2


def test_dynamic_response_always_uses_normal_provider_without_template_cache(tmp_path: Path) -> None:
    tts = RecordingTts()
    plan = DynamicVoiceResponsePlan.model_validate(
        {
            "kind": "dynamic",
            "responseType": "dialogue.dynamic",
            "locale": "en",
            "voiceProfileId": "velora",
            "voiceProfileRevision": VOICE_REVISION,
            "catalogRevision": "voice-responses-v1",
            "renderedText": "This remains a normal dynamic response.",
        }
    )

    first = resolver(tmp_path, tts).resolve(plan)

    assert first.source == "normal_tts"
    assert first.cache_hit is False
    assert tts.calls == [(plan.rendered_text, "velora", "en")]


def test_slot_contract_rejects_unknown_types() -> None:
    with pytest.raises(ValueError):
        VoiceResponseSlot.model_validate({"type": "invented", "value": "Gamingraum"})
