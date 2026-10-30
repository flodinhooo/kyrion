"""Read-only Flyway compatibility gate for the reviewed running artifact."""

import json
import re
import subprocess
import sys
import zipfile
import zlib
from pathlib import Path


def query(sql: str) -> str:
    result = subprocess.run(
        [
            "docker.exe",
            "exec",
            "kyrion-postgres",
            "sh",
            "-c",
            'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -Atqc "$1"',
            "sh",
            sql,
        ],
        capture_output=True,
        text=True,
        timeout=20,
        check=True,
    )
    return result.stdout.strip()


def verify(artifact: Path) -> dict:
    installed = query(
        "SELECT version,checksum,success FROM flyway_schema_history WHERE type='SQL' ORDER BY installed_rank"
    )
    with zipfile.ZipFile(artifact) as archive:
        migrations = {}
        for name in archive.namelist():
            match = re.search(
                r"BOOT-INF/classes/db/migration/V(.+?)__[^/]+\.sql$", name
            )
            if match:
                content = archive.read(name).decode("utf-8-sig")
                crc = zlib.crc32("".join(content.splitlines()).encode("utf-8"))
                migrations[match[1].replace("_", ".")] = (
                    crc if crc < 2 ** 31 else crc - 2 ** 32
                )
    mismatches = []
    versions = []
    for row in installed.splitlines():
        version, checksum, success = row.split("|")
        versions.append(version)
        if success != "t" or migrations.get(version) != int(checksum):
            mismatches.append(version)
    pending = sorted(set(migrations) - set(versions))
    leases = int(
        query(
            "SELECT count(*) FROM calendar_sync_schedule WHERE lease_until > CURRENT_TIMESTAMP"
        )
    )
    return {
        "installedMigrations": len(versions),
        "mismatchedVersions": mismatches,
        "pendingVersions": pending,
        "activeSyncLeases": leases,
        "safe": bool(versions) and not mismatches and not pending and leases == 0,
    }


if __name__ == "__main__":
    try:
        summary = verify(Path(sys.argv[1]))
    except (
            OSError,
            ValueError,
            IndexError,
            zipfile.BadZipFile,
            subprocess.SubprocessError,
    ) as error:
        summary = {"safe": False, "code": type(error).__name__}
    print(json.dumps(summary))
    raise SystemExit(0 if summary["safe"] else 1)
