#!/usr/bin/env python3
"""Validate a release manifest and its immutable artifact digests."""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path

MAX_MANIFEST = 1024 * 1024


def validate(root: Path, manifest_path: Path) -> dict:
  if manifest_path.is_symlink() or manifest_path.stat().st_size > MAX_MANIFEST:
    raise ValueError("E_MANIFEST: invalid manifest file")
  manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
  required = {"schemaVersion", "release", "architecture", "artifacts"}
  if set(manifest) != required or manifest["schemaVersion"] != 1 or manifest["architecture"] != "linux/arm64":
    raise ValueError("E_MANIFEST: unsupported or unknown manifest fields")
  if not isinstance(manifest["release"], str) or not manifest["release"] or "latest" in manifest["release"].lower():
    raise ValueError("E_RELEASE: immutable release version required")
  if not isinstance(manifest["artifacts"], list) or not manifest["artifacts"]:
    raise ValueError("E_ARTIFACTS: artifact list is empty")
  for item in manifest["artifacts"]:
    if set(item) != {"name", "sha256", "bytes"} or not isinstance(item["name"], str):
      raise ValueError("E_ARTIFACT: malformed artifact")
    path = (root / item["name"]).resolve()
    if root.resolve() not in path.parents or path.is_symlink() or not path.is_file():
      raise ValueError(f"E_ARTIFACT: missing or unsafe artifact {item['name']}")
    if path.stat().st_size != item["bytes"]:
      raise ValueError(f"E_DIGEST: size mismatch for {item['name']}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != item["sha256"]:
      raise ValueError(f"E_DIGEST: checksum mismatch for {item['name']}")
  return manifest


def main() -> int:
  parser = argparse.ArgumentParser();
  parser.add_argument("root", type=Path);
  parser.add_argument("manifest", type=Path)
  args = parser.parse_args()
  try:
    print(json.dumps(validate(args.root, args.manifest), sort_keys=True)); return 0
  except (OSError, ValueError, json.JSONDecodeError) as e:
    print(str(e), file=sys.stderr); return 2


if __name__ == "__main__": raise SystemExit(main())
