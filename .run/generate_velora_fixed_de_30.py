"""Generate review-only German Velora fixed-response candidates with Qwen voice cloning."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel

MODEL = "/training/models/qwen3-tts/voice-clone-base"
REFERENCE = Path("/mnt/e/dev/Kyrion/kyrion/.run/velora-female-options/F_weiblich_klar.wav")
REFERENCE_SHA256 = "d2afdc5faa3fb6cc41756daaaac3db63c30679e3bcd3e87f6dab0055d08dad09"
REFERENCE_TEXT = (
    "Guten Morgen. Ich bin Velora. Für heute stehen noch zwei Aufgaben auf deiner Liste. "
    "Möchtest du zuerst den Überblick hören, oder sollen wir direkt anfangen?"
)
OUTPUT = Path("/mnt/e/Kyrion/Data/voice-production/velora-fixed-de-v1/qwen-1.7b-raw-candidates")
CANDIDATES_PER_LINE = 2

LINES = [
    ("01_session.greeting_neutral-01", "Hallo."),
    ("02_session.greeting_warm-01", "Hallo, schön dich zu hören."),
    ("03_session.farewell_neutral-01", "Bis später."),
    ("04_session.farewell_warm-01", "Mach’s gut."),
    ("05_dialogue.acknowledged_neutral-01", "Okay."),
    ("06_dialogue.acknowledged_neutral-02", "Alles klar."),
    ("07_dialogue.acknowledged_neutral-03", "Verstanden."),
    ("08_command.succeeded_neutral-01", "Erledigt."),
    ("09_command.succeeded_neutral-02", "Ist erledigt."),
    ("10_command.succeeded_warm-01", "Das hat funktioniert."),
    ("11_command.failed_neutral-01", "Das hat nicht funktioniert."),
    ("12_command.failed_neutral-02", "Der Befehl ist fehlgeschlagen."),
    ("13_command.failed_neutral-03", "Ich konnte die Aktion nicht ausführen."),
    ("14_target.not_found_neutral-01", "Ich konnte das Ziel nicht finden."),
    ("15_target.not_found_neutral-02", "Dieses Gerät oder diesen Raum konnte ich nicht finden."),
    ("16_target.ambiguous_neutral-01", "Das Ziel ist nicht eindeutig."),
    ("17_target.ambiguous_neutral-02", "Ich habe mehrere passende Ziele gefunden."),
    ("18_device.offline_neutral-01", "Das Gerät ist momentan nicht erreichbar."),
    ("19_device.offline_neutral-02", "Ich kann das Gerät gerade nicht erreichen."),
    ("20_action.denied_neutral-01", "Diese Aktion ist nicht erlaubt."),
    ("21_action.denied_neutral-02", "Ich darf diese Aktion nicht ausführen."),
    ("22_command.partially_succeeded_neutral-01", "Die Aktion war nur teilweise erfolgreich."),
    ("23_command.partially_succeeded_neutral-02", "Ein Teil wurde ausgeführt, aber nicht alles."),
    ("24_action.cancelled_neutral-01", "Die Aktion wurde abgebrochen."),
    ("25_action.cancelled_neutral-02", "Okay, ich habe den Vorgang abgebrochen."),
    ("26_action.timeout_neutral-01", "Die Aktion hat zu lange gedauert."),
    ("27_action.timeout_neutral-02", "Ich habe keine rechtzeitige Rückmeldung erhalten."),
    ("28_action.stale_neutral-01", "Diese Anfrage ist nicht mehr aktuell."),
    ("29_proposal.unavailable_neutral-01", "Ich konnte die Aktion gerade nicht sicher prüfen."),
    ("30_proposal.unavailable_neutral-02", "Die Aktionsprüfung ist momentan nicht verfügbar."),
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    if sha256(REFERENCE) != REFERENCE_SHA256:
        raise RuntimeError("Canonical velora-f reference checksum mismatch")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    catalog = {
        "schemaVersion": 1,
        "status": "review_only",
        "model": MODEL,
        "reference": str(REFERENCE),
        "referenceSha256": REFERENCE_SHA256,
        "referenceText": REFERENCE_TEXT,
        "candidatesPerLine": CANDIDATES_PER_LINE,
        "lines": [{"id": key, "text": text} for key, text in LINES],
    }
    (OUTPUT / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    model = Qwen3TTSModel.from_pretrained(
        MODEL, device_map="cuda:0", dtype=torch.float16, attn_implementation="sdpa"
    )
    prompt = model.create_voice_clone_prompt(ref_audio=str(REFERENCE), ref_text=REFERENCE_TEXT)
    results: list[dict[str, object]] = []
    for line_index, (key, text) in enumerate(LINES, start=1):
        for candidate in range(1, CANDIDATES_PER_LINE + 1):
            target = OUTPUT / f"{key}__candidate-{candidate:02d}.wav"
            if target.exists():
                print(f"SKIP {target.name}", flush=True)
                continue
            seed = 2026081900 + line_index * 10 + candidate
            torch.manual_seed(seed)
            started = time.perf_counter()
            wavs, sample_rate = model.generate_voice_clone(
                text=text, language="German", voice_clone_prompt=prompt, max_new_tokens=1024
            )
            sf.write(target, wavs[0], sample_rate, subtype="PCM_16")
            duration = len(wavs[0]) / sample_rate
            result = {
                "id": key, "text": text, "candidate": candidate, "seed": seed,
                "path": str(target), "sampleRateHz": sample_rate, "durationSeconds": duration,
                "generationSeconds": time.perf_counter() - started, "sha256": sha256(target),
            }
            results.append(result)
            with (OUTPUT / "generation-results.ndjson").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(result, ensure_ascii=False) + "\n")
            print(f"DONE {target.name} duration={duration:.2f}s", flush=True)


if __name__ == "__main__":
    main()
