"""Register one owner-reviewed fixed Velora WAV in the response manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import wave
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--locale", choices=("de", "en"), required=True)
    parser.add_argument("--response-key", required=True)
    parser.add_argument("--variant-id", required=True)
    parser.add_argument("--owner-approved", action="store_true", required=True)
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    source = args.source.resolve()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    key = (args.locale, args.response_key, args.variant_id)
    pending = payload.get("pendingAssets", [])
    item = next(
        (
            candidate
            for candidate in pending
            if (
                candidate.get("locale"),
                candidate.get("responseKey"),
                candidate.get("variantId"),
            )
            == key
        ),
        None,
    )
    if item is None:
        raise SystemExit("Asset is not in the pending manifest inventory")

    with wave.open(str(source), "rb") as wav_file:
        if (
            wav_file.getcomptype() != "NONE"
            or wav_file.getsampwidth() != 2
            or wav_file.getnchannels() != 1
            or wav_file.getframerate() != 24_000
        ):
            raise SystemExit("Expected mono PCM16 WAV at 24 kHz")

    relative = Path("assets") / "velora" / args.locale / args.response_key / f"{args.variant_id}.wav"
    target = manifest_path.parent / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    audio = target.read_bytes()
    payload.setdefault("assets", []).append(
        {
            "catalogRevision": payload["catalogRevision"],
            "voiceProfileId": "velora",
            "voiceProfileRevision": payload["voiceProfiles"]["velora"],
            "locale": args.locale,
            "responseKey": args.response_key,
            "variantId": args.variant_id,
            "text": item["text"],
            "path": relative.as_posix(),
            "sha256": hashlib.sha256(audio).hexdigest(),
            "reviewedBy": "owner",
        }
    )
    payload["pendingAssets"] = [candidate for candidate in pending if candidate is not item]
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(target)


if __name__ == "__main__":
    main()
