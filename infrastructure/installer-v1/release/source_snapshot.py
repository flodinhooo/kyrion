"""Seal only public package inputs before invoking a native compiler."""

import hashlib
from pathlib import Path


def stage_sources(root: Path, target: Path, names) -> dict[str, str]:
    from host import reject_links
    from native_bundle import safe_member

    if target.exists() or len(names) != len(set(names)):
        raise ValueError("E_NATIVE_SOURCE_SNAPSHOT")
    expected = {}
    for name in names:
        # Reuse the reviewed path rules with a public prefix; installer source
        # members themselves can be flat, unlike native runtime bundle members.
        safe_member("app/core/" + name)
        if any(part.startswith(".") for part in Path(name).parts):
            raise ValueError("E_NATIVE_SOURCE_SNAPSHOT")
        source = root / name
        reject_links(source)
        if not source.is_file() or source.stat().st_size > 1024 ** 2:
            raise ValueError("E_NATIVE_SOURCE_SNAPSHOT")
        expected[name] = hashlib.sha256(source.read_bytes()).hexdigest()
    target.mkdir(mode=0o700)
    for name, digest in expected.items():
        source = root / name
        reject_links(source)
        raw = source.read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("E_NATIVE_SOURCE_CHANGED")
        destination = target / name
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with destination.open("xb") as stream:
            stream.write(raw)
    return expected
