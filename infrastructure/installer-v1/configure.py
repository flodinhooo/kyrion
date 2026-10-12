#!/usr/bin/env python3
"""Create fresh-install secrets and protected configuration atomically."""
from __future__ import annotations
import argparse, base64, json, os, secrets, stat
from pathlib import Path


def write_private(path: Path, value: str) -> None:
  path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
  if path.exists() or path.is_symlink(): raise ValueError(f"E_EXISTING_STATE: {path}")
  tmp = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
  fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
  try:
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
      handle.write(value + "\n"); handle.flush(); os.fsync(handle.fileno())
    os.replace(tmp, path)
  finally:
    if tmp.exists(): tmp.unlink()


def main() -> int:
  p = argparse.ArgumentParser();
  p.add_argument("--secrets-dir", type=Path, required=True);
  p.add_argument("--hostname", required=True);
  p.add_argument("--release", required=True);
  p.add_argument("--output", type=Path, required=True)
  a = p.parse_args();
  a.secrets_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
  if any(a.secrets_dir.iterdir()) or a.output.exists(): raise SystemExit(
    "E_EXISTING_STATE: configuration target is not empty")
  bootstrap = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")
  write_private(a.secrets_dir / "bootstrap.secret", bootstrap);
  write_private(a.secrets_dir / "credential.key", base64.urlsafe_b64encode(secrets.token_bytes(32)).decode());
  write_private(a.secrets_dir / "audit-integrity.key", base64.urlsafe_b64encode(secrets.token_bytes(32)).decode());
  write_private(a.secrets_dir / "postgres-password", secrets.token_urlsafe(32))
  a.output.parent.mkdir(mode=0o700, parents=True, exist_ok=True);
  a.output.write_text(json.dumps(
    {"hostname": a.hostname, "release": a.release, "bootstrap_secret_file": str(a.secrets_dir / "bootstrap.secret")},
    indent=2) + "\n", encoding="utf-8");
  os.chmod(a.output, 0o600)
  print(json.dumps({"ok": True, "bootstrap_secret_file": str(a.secrets_dir / "bootstrap.secret")}));
  return 0


if __name__ == "__main__": raise SystemExit(main())
