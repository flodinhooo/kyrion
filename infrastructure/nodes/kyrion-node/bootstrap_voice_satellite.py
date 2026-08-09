"""Bootstrap a voice-only credential from an already enrolled local gateway."""

from __future__ import annotations

import argparse
import json
import os
import pwd
import urllib.request
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gateway-config", type=Path, required=True)
    parser.add_argument("--voice-config", type=Path, required=True)
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--owner", required=True)
    arguments = parser.parse_args()

    gateway = json.loads(arguments.gateway_config.read_text(encoding="utf-8"))
    request = urllib.request.Request(
        f"{gateway['core_url'].rstrip('/')}/v1/voice-satellite/bootstrap-from-gateway",
        data=json.dumps({"hostname": os.uname().nodename, "runtimeVersion": "0.1.0"}).encode(),
        headers={
            "Authorization": f"Bearer {gateway['gateway_token']}",
            "X-Kyrion-Node-Id": gateway["node_id"],
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        enrolled = json.loads(response.read())

    account = pwd.getpwnam(arguments.owner)
    arguments.token_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    arguments.token_file.write_text(enrolled["satelliteToken"], encoding="utf-8")
    os.chmod(arguments.token_file, 0o600)

    config = json.loads(arguments.voice_config.read_text(encoding="utf-8"))
    config.update(
        {
            "core_url": gateway["core_url"],
            "satellite_id": enrolled["satelliteId"],
            "credential_file": str(arguments.token_file),
            "locale": "de",
            "speech_start_timeout_seconds": 6.0,
            "speech_end_silence_seconds": 0.8,
            "utterance_max_seconds": 20.0,
        }
    )
    temporary = arguments.voice_config.with_suffix(".tmp")
    temporary.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(arguments.voice_config)
    for path in (arguments.token_file.parent, arguments.token_file, arguments.voice_config):
        os.chown(path, account.pw_uid, account.pw_gid)
    print(enrolled["satelliteId"])


if __name__ == "__main__":
    main()
