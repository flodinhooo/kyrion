"""Artifact-bound Flyway only. Default: read-only plan. No application startup."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

LIBRARY = re.compile(
    r"(?:flyway-core|flyway-database-postgresql|postgresql|jackson-core|"
    r"jackson-databind|jackson-annotations|commons-logging)-[0-9][A-Za-z0-9.+_-]*\.jar"
)
MIGRATION = re.compile(r"BOOT-INF/classes/db/migration/V([0-9]+)__[A-Za-z0-9_]+\.sql")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, code):
    if not condition:
        raise ValueError(code)


def extract_artifact(artifact, expected, directory):
    # Read once: hashing and extraction use the identical bytes even if the path changes.
    import io

    data = artifact.read_bytes()
    require(
        re.fullmatch(r"[a-f0-9]{64}", expected) and digest(data) == expected,
        "ARTIFACT_HASH_MISMATCH",
    )
    catalog = {}
    libraries = {}
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), "ARTIFACT_DUPLICATE_ENTRY")
        for name in names:
            if name.startswith("BOOT-INF/classes/db/migration/") and not name.endswith(
                "/"
            ):
                match = MIGRATION.fullmatch(name)
                require(match is not None, "ARTIFACT_UNEXPECTED_MIGRATION")
                version = int(match[1])
                require(version not in catalog, "ARTIFACT_DUPLICATE_VERSION")
                content = archive.read(name)
                catalog[version] = {
                    "file": name.rsplit("/", 1)[1],
                    "sha256": digest(content),
                }
                (directory / "sql" / catalog[version]["file"]).write_bytes(content)
            if name.startswith("BOOT-INF/lib/") and LIBRARY.fullmatch(
                name.rsplit("/", 1)[1]
            ):
                require(name.count("/") == 2, "ARTIFACT_LIBRARY_PATH_INVALID")
                content = archive.read(name)
                filename = name.rsplit("/", 1)[1]
                libraries[filename] = digest(content)
                (directory / "lib" / filename).write_bytes(content)
    require(
        sorted(catalog) in tuple(list(range(1, end + 1)) for end in (45, 46, 47, 48, 49)),
        "ARTIFACT_CATALOG_NOT_V1_TO_V45_THROUGH_V49",
    )
    for prefix in ("flyway-core-", "flyway-database-postgresql-", "postgresql-"):
        require(
            sum(name.startswith(prefix) for name in libraries) == 1,
            "ARTIFACT_LIBRARY_INVALID",
        )
    return {
        "migrations": {str(k): catalog[k] for k in sorted(catalog)},
        "libraries": libraries,
    }


def run(args):
    settings = json.loads(args.connection_file.read_text(encoding="utf-8-sig"))
    require(
        set(settings)
        <= {"host", "port", "database", "user", "password", "sslmode", "sslrootcert"},
        "CONNECTION_FIELDS_INVALID",
    )
    for key in ("host", "database", "user", "password"):
        require(
            isinstance(settings.get(key), str) and settings[key],
            "CONNECTION_FIELDS_INVALID",
        )
    require(
        re.fullmatch(r"[A-Za-z0-9_.-]+", settings["host"]), "CONNECTION_HOST_INVALID"
    )
    require(
        re.fullmatch(r"[A-Za-z0-9_]+", settings["database"]),
        "CONNECTION_DATABASE_INVALID",
    )
    require(
        type(settings.get("port")) is int and 1 <= settings["port"] <= 65535,
        "CONNECTION_PORT_INVALID",
    )
    mode = settings.setdefault("sslmode", "verify-full")
    require(
        mode == "verify-full"
        or (mode == "disable" and settings["host"] == "127.0.0.1"),
        "CONNECTION_TLS_REQUIRED",
    )
    approved = None
    if args.apply:
        require(
            args.approve_plan_sha256 and args.expected_target, "APPLY_APPROVAL_REQUIRED"
        )
        data = args.plan.read_bytes()
        require(digest(data) == args.approve_plan_sha256, "PLAN_HASH_MISMATCH")
        approved = json.loads(data)
        require(
            approved.get("format") == "kyrion-schema-plan-v1"
            and approved.get("artifactSha256") == args.artifact_sha256,
            "PLAN_ARTIFACT_MISMATCH",
        )
        require(
            approved.get("state", {}).get("targetIdentity") == args.expected_target,
            "PLAN_TARGET_MISMATCH",
        )
    else:
        require(
            not args.approve_plan_sha256 and not args.expected_target,
            "APPROVAL_WITHOUT_APPLY",
        )
        require(not args.plan.exists(), "PLAN_ALREADY_EXISTS")
    java_home = args.java_home
    require(java_home is not None, "JDK_21_REQUIRED")
    suffix = ".exe" if os.name == "nt" else ""
    java = str(java_home / "bin" / ("java" + suffix))
    javac = str(java_home / "bin" / ("javac" + suffix))
    version = subprocess.run([java, "-version"], capture_output=True, check=False)
    require(
        version.returncode == 0 and re.search(rb'version "21[.+-]', version.stderr),
        "JDK_21_REQUIRED",
    )
    with tempfile.TemporaryDirectory(prefix="kyrion-schema-") as temporary:
        directory = Path(temporary)
        (directory / "sql").mkdir()
        (directory / "lib").mkdir()
        if approved:
            require(
                approved.get("targetVersion") == args.target_version,
                "PLAN_TARGET_VERSION_MISMATCH",
            )
        catalog = extract_artifact(args.artifact, args.artifact_sha256, directory)
        require(
            str(args.target_version) in catalog["migrations"], "ARTIFACT_TARGET_MISSING"
        )
        if approved:
            require(approved.get("catalog") == catalog, "PLAN_CATALOG_MISMATCH")
        source = Path(__file__).with_name("CoreSchemaMigration.java")
        java_source = source.read_bytes()
        tool_hash = digest(java_source + Path(__file__).read_bytes())
        if approved:
            require(approved.get("toolSha256") == tool_hash, "PLAN_TOOL_MISMATCH")
        classpath = os.pathsep.join(
            str(p) for p in sorted((directory / "lib").glob("*.jar"))
        )
        source = directory / "CoreSchemaMigration.java"
        source.write_bytes(java_source)
        compiled = subprocess.run(
            [
                javac,
                "-encoding",
                "UTF-8",
                "-cp",
                classpath,
                "-d",
                str(directory),
                str(source),
            ],
            capture_output=True,
            check=False,
        )
        require(compiled.returncode == 0, "MIGRATION_TOOL_COMPILE_FAILED")
        request = {
            "connection": settings,
            "location": str(directory / "sql"),
            "apply": args.apply,
            "targetVersion": args.target_version,
            "expectedState": approved["state"] if approved else None,
        }
        # Secret-bearing settings travel only through stdin; discard all third-party diagnostics.
        result = subprocess.run(
            [
                java,
                "-cp",
                str(directory) + os.pathsep + classpath,
                "CoreSchemaMigration",
            ],
            input=json.dumps(request),
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
        lines = [
            line[14:]
            for line in result.stdout.splitlines()
            if line.startswith("KYRION_RESULT:")
        ]
        require(result.returncode == 0 and len(lines) == 1, "MIGRATION_TOOL_FAILED")
        response = json.loads(lines[0])
        require(response.get("ok"), response.get("code", "MIGRATION_TOOL_FAILED"))
        report = {
            "format": "kyrion-schema-result-v1"
            if args.apply
            else "kyrion-schema-plan-v1",
            "artifactSha256": args.artifact_sha256,
            "toolSha256": tool_hash,
            "catalog": catalog,
            "targetVersion": args.target_version,
            **response,
        }
        if args.apply:
            print(json.dumps(report, sort_keys=True))
        else:
            with args.plan.open("x", encoding="utf-8", newline="\n") as output:
                output.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
            print(
                json.dumps(
                    {
                        "planSha256": digest(args.plan.read_bytes()),
                        "targetIdentity": report["state"]["targetIdentity"],
                        "fromVersion": report["state"]["version"],
                        "toVersion": args.target_version,
                    }
                )
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--artifact-sha256", required=True)
    parser.add_argument("--connection-file", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument(
        "--java-home",
        type=Path,
        default=Path(os.environ["JAVA_HOME"]) if os.environ.get("JAVA_HOME") else None,
    )
    parser.add_argument("--target-version", type=int, choices=(45, 46, 47, 48, 49), default=45)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approve-plan-sha256")
    parser.add_argument("--expected-target")
    args = parser.parse_args()
    try:
        run(args)
    except Exception as error:  # noqa: BLE001 -- mandatory redaction at the operator boundary
        # Never echo driver/compiler/OS errors: they can contain credentials or SQL/data.
        code = (
            str(error)
            if isinstance(error, ValueError)
            and re.fullmatch(r"[A-Z][A-Z0-9_]+", str(error))
            else "SCHEMA_TOOL_FAILED"
        )
        print(json.dumps({"ok": False, "code": code}))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
