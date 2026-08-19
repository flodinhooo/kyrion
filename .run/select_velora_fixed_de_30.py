"""Materialize the owner's selected Velora German review candidates without registering them."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

SOURCE = Path("E:/Kyrion/Data/voice-production/velora-fixed-de-v1/qwen-1.7b-raw-candidates")
TARGET = Path("E:/Kyrion/Data/voice-production/velora-fixed-de-v1/selected-pending-final-approval")
SELECTIONS = [1, 1, 2, 1, 2, 2, 2, 1, 2, 2, 2, 1, 2, 2, 2, 2, 1, 2, 1, 1, 2, 1, 1, 1, 2, 2, 1, 2, 2, 2]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    catalog = json.loads((SOURCE / "catalog.json").read_text(encoding="utf-8"))
    if len(catalog["lines"]) != len(SELECTIONS):
        raise RuntimeError("Selection count does not match catalog")
    TARGET.mkdir(parents=True, exist_ok=True)
    manifest = []
    playlist = ["#EXTM3U"]
    for index, (line, candidate) in enumerate(zip(catalog["lines"], SELECTIONS, strict=True), start=1):
        matches = list(SOURCE.glob(f"{line['id']}__candidate-{candidate:02d}.wav"))
        if len(matches) != 1:
            raise RuntimeError(f"Expected exactly one candidate for {line['id']}")
        source = matches[0]
        target = TARGET / f"{line['id']}.wav"
        if target.exists() and sha256(target) != sha256(source):
            raise RuntimeError(f"Refusing to overwrite changed selection: {target}")
        shutil.copy2(source, target)
        playlist.append(target.name)
        manifest.append({
            "order": index,
            "id": line["id"],
            "text": line["text"],
            "selectedCandidate": candidate,
            "source": str(source),
            "selectedPath": str(target),
            "sha256": sha256(target),
            "status": "selected_pending_explicit_final_owner_approval",
        })
    (TARGET / "selection-manifest.json").write_text(
        json.dumps({"schemaVersion": 1, "items": manifest}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (TARGET / "listen-selected-in-order.m3u8").write_text("\n".join(playlist) + "\n", encoding="utf-8")
    (TARGET / "README.md").write_text(
        "# Selected Velora German candidates\n\n"
        "These 30 files reflect the owner's candidate choices. They remain pending explicit final owner approval.\n"
        "No file has been registered in the production fixed-response manifest.\n\n"
        "Listen to `listen-selected-in-order.m3u8` once more from start to finish before final approval.\n",
        encoding="utf-8",
    )
    print(json.dumps({"selected": len(manifest), "target": str(TARGET)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
