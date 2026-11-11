"""Actual encrypted backup/restore drill using only new network-none databases."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from recovery import create_archive, crypto, verify_database
from runtime import execute


def main(image_id: str) -> None:
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
        raise ValueError("E_IMAGE_PIN")
    with tempfile.TemporaryDirectory(prefix="kyrion-real-restore-") as directory:
        root = Path(directory)
        os.chmod(root, 0o700)
        name = "kyrion-source-fixture-" + uuid.uuid4().hex
        container = execute(
            [
                "docker",
                "run",
                "-d",
                "--name",
                name,
                "--network",
                "none",
                "--label",
                "io.kyrion.restore-target=true",
                "--tmpfs",
                "/var/lib/postgresql/data:rw,size=536870912",
                "-e",
                "POSTGRES_HOST_AUTH_METHOD=trust",
                "-e",
                "POSTGRES_USER=kyrion",
                "-e",
                "POSTGRES_DB=kyrion",
                image_id,
            ]
        ).strip()
        if not re.fullmatch(r"[a-f0-9]{64}", container):
            raise ValueError("E_RESTORE_CONTAINER")
        try:
            for _ in range(30):
                ready = subprocess.run(
                    ["docker", "exec", container, "pg_isready", "-U", "kyrion"],
                    capture_output=True,
                    timeout=5,
                    check=False,
                )
                if ready.returncode == 0:
                    break
                time.sleep(1)
            else:
                raise ValueError("E_FIXTURE_NOT_READY")
            sql = "CREATE TABLE flyway_schema_history(version varchar(50),success boolean); INSERT INTO flyway_schema_history VALUES('46',true); CREATE TABLE user_account(id integer primary key,label text); INSERT INTO user_account VALUES(1,'isolated owner fixture'); CREATE TABLE kyrion_space(id integer); INSERT INTO kyrion_space VALUES(1); CREATE TABLE activity_event(id integer); INSERT INTO activity_event VALUES(1),(2);"
            execute(
                [
                    "docker",
                    "exec",
                    container,
                    "psql",
                    "-U",
                    "kyrion",
                    "-d",
                    "kyrion",
                    "-v",
                    "ON_ERROR_STOP=1",
                    "-c",
                    sql,
                ]
            )
            dump = root / "database.dump"
            with dump.open("xb") as stream:
                subprocess.run(
                    [
                        "docker",
                        "exec",
                        container,
                        "pg_dump",
                        "-U",
                        "kyrion",
                        "-d",
                        "kyrion",
                        "--format=custom",
                        "--no-owner",
                        "--no-acl",
                    ],
                    stdout=stream,
                    stderr=subprocess.PIPE,
                    check=True,
                    timeout=60,
                )
        finally:
            execute(["docker", "rm", "-f", container])
        original_key = root / "original.key"
        original_key.write_bytes(os.urandom(32))
        archive = root / "backup.tar"
        create_archive(
            {"database.dump": dump, "secrets/credential.key": original_key},
            {
                "postgresMajor": 17,
                "schema": 46,
                "fixture": True,
                "verificationCounts": {"users": 1, "spaces": 1, "audit": 2},
            },
            archive,
        )
        encrypted = root / "backup.gpg"
        password = "synthetic-only-" + uuid.uuid4().hex
        crypto(archive, encrypted, password)
        result = verify_database(encrypted, password, image_id)
        if result.get("databaseRestoreVerified") is not True:
            raise ValueError("E_FIXTURE_RESTORE")
        print(
            json.dumps(
                {
                    "fixture": True,
                    "actualPostgresRestore": result,
                    "productionDataUsed": False,
                    "applicationRecoveryAccepted": False,
                }
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--postgres-image", required=True)
    main(parser.parse_args().postgres_image)
