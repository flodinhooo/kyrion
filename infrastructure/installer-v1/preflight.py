#!/usr/bin/env python3
"""Read-only checks used before a Kyrion fresh installation."""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import socket
import sys
from pathlib import Path

MIN_FREE = 12 * 1024 ** 3
MIN_RAM = 4 * 1024 ** 3


class PreflightError(Exception):
  pass


def fail(code: str, message: str) -> None:
  raise PreflightError(f"{code}: {message}")


def check(args: argparse.Namespace) -> dict[str, object]:
  if platform.system() != "Linux":
    fail("E_PLATFORM", "Installer v1 requires Linux.")
  machine = platform.machine().lower()
  if machine not in {"aarch64", "arm64"}:
    fail("E_ARCH", f"Unsupported architecture: {machine}; expected ARM64.")
  os_release = Path("/etc/os-release")
  if not os_release.is_file():
    fail("E_OS", "Cannot identify the operating system.")
  fields = dict(line.split("=", 1) for line in os_release.read_text().splitlines() if "=" in line)
  system_id = fields.get("ID", "").strip('"')
  if system_id not in {"debian", "raspbian"}:
    fail("E_OS", f"Unsupported operating system: {system_id or 'unknown'}.")
  target = Path(args.install_dir)
  target_parent = target.parent
  if target.exists() and (target.is_symlink() or not target.is_dir()):
    fail("E_TARGET", "Installation directory is not a real directory.")
  if target.exists() and any(target.iterdir()):
    fail("E_EXISTING_STATE", "Installation directory is not empty; refusing to overwrite it.")
  if target_parent.is_symlink():
    fail("E_TARGET", "Installation parent must not be a symlink.")
  for path in (Path(args.data_dir), Path(args.secrets_dir)):
    if path.exists() and (path.is_symlink() or (path.is_dir() and any(path.iterdir()))):
      fail("E_EXISTING_STATE", f"Persistent target is populated: {path}")
  if shutil.disk_usage(target_parent).free < MIN_FREE:
    fail("E_DISK", "At least 12 GiB of free space is required.")
  meminfo = Path("/proc/meminfo")
  if meminfo.is_file():
    mem = next(
      (int(line.split()[1]) * 1024 for line in meminfo.read_text().splitlines() if line.startswith("MemTotal:")), 0)
    if mem < MIN_RAM:
      fail("E_MEMORY", "At least 4 GiB RAM is required.")
  for command in ("docker", "curl", "openssl"):
    if not shutil.which(command):
      fail("E_TOOL", f"Required command is missing: {command}")
  if not shutil.which("docker-compose") and not Path("/usr/libexec/docker/cli-plugins/docker-compose").exists():
    fail("E_COMPOSE", "Docker Compose v2 plugin is required.")
  try:
    socket.getaddrinfo(args.hostname, 443)
  except socket.gaierror:
    fail("E_HOSTNAME", f"Hostname cannot be resolved locally: {args.hostname}")
  return {"platform": system_id, "architecture": machine, "hostname": args.hostname,
          "free_bytes": shutil.disk_usage(target_parent).free}


def main() -> int:
  parser = argparse.ArgumentParser()
  parser.add_argument("--install-dir", required=True)
  parser.add_argument("--data-dir", required=True)
  parser.add_argument("--secrets-dir", required=True)
  parser.add_argument("--hostname", required=True)
  args = parser.parse_args()
  try:
    print(json.dumps({"ok": True, "checks": check(args)}, sort_keys=True))
    return 0
  except PreflightError as error:
    print(json.dumps({"ok": False, "error": str(error)}), file=sys.stderr)
    return 2


if __name__ == "__main__":
  raise SystemExit(main())
