import csv
from pathlib import Path
from runpy import run_path

SCRIPT = Path(__file__).parents[1] / "training" / "merge_reviewed_sessions.py"
MODULE = run_path(str(SCRIPT))


def make_session(root: Path, name: str, label: str) -> Path:
    session = root / name / "clips"
    (session / label).mkdir(parents=True)
    (session / label / "clip-001.wav").write_bytes(b"audio")
    with (session / "manifest.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["file", "start_seconds", "end_seconds", "duration_seconds", "label"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "file": "clip-001.wav",
                "start_seconds": "0.000",
                "end_seconds": "1.000",
                "duration_seconds": "1.000",
                "label": label,
            }
        )
    return session


def test_merge_preserves_session_identity(tmp_path: Path) -> None:
    positive = make_session(tmp_path, "positive-session", "positive")
    negative = make_session(tmp_path, "negative-session", "negative")

    counts = MODULE["merge"]([positive, negative], tmp_path / "merged")

    assert counts == {"positive": 1, "negative": 1, "excluded": 0}
    assert (tmp_path / "merged/positive/positive-session-clip-001.wav").exists()
    assert (tmp_path / "merged/negative/negative-session-clip-001.wav").exists()
