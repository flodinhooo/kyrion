"""Actual binary COPY roundtrip in fresh disposable native PostgreSQL databases."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import portable_database as portable

SCHEMA = """CREATE TABLE flyway_schema_history(installed_rank integer PRIMARY KEY,version text,description text,type text,script text,checksum integer,success boolean);
INSERT INTO flyway_schema_history VALUES(1,'1','synthetic','SQL','V1.sql',123,true);
CREATE TABLE parent(id bigserial PRIMARY KEY,payload text NOT NULL,binary_data bytea NOT NULL);
CREATE TABLE child(id integer PRIMARY KEY,parent_id bigint NOT NULL REFERENCES parent(id),quantity integer NOT NULL CHECK(quantity>0));"""


def exercise(bin_directory: Path) -> dict:
    if os.name == "posix" and os.geteuid() == 0:
        raise ValueError("E_FIXTURE_UNPRIVILEGED_REQUIRED")
    suffix = ".exe" if os.name == "nt" else ""
    tools = {
        name: bin_directory / (name + suffix) for name in ("initdb", "pg_ctl", "psql")
    }
    if not all(path.is_file() for path in tools.values()):
        raise ValueError("E_FIXTURE_POSTGRES_REQUIRED")
    with tempfile.TemporaryDirectory(prefix="kyrion-portable-database-") as directory:
        root = Path(directory)
        environment = {
            key: value
            for key, value in os.environ.items()
            if key.upper() in {"SYSTEMROOT", "WINDIR", "PATH", "LANG", "LC_ALL"}
        }
        environment.update(
            HOME=str(root),
            USERPROFILE=str(root),
            APPDATA=str(root),
            TEMP=str(root),
            TMP=str(root),
            PGCONNECT_TIMEOUT="5",
            PGCLIENTENCODING="UTF8",
        )

        def command(name, arguments, **options):
            if name == "pg_ctl":
                # Windows pg_ctl's detached launcher may retain inherited pipe
                # handles. Use a private file, never captured pipes, for daemons.
                options.pop("stdout", None)
                with (root / "control.log").open("ab") as log:
                    result = subprocess.run(
                        [str(tools[name]), *arguments],
                        cwd=root,
                        env=environment,
                        stdin=subprocess.DEVNULL,
                        stdout=log,
                        stderr=log,
                        timeout=60,
                        check=False,
                        creationflags=subprocess.CREATE_NO_WINDOW
                        if os.name == "nt"
                        else 0,
                    )
                if result.returncode:
                    raise ValueError("E_PORTABLE_DATABASE_FIXTURE_" + name.upper())
                return b""
            result = subprocess.run(
                [str(tools[name]), *arguments],
                cwd=root,
                env=environment,
                stdin=options.pop("stdin", subprocess.DEVNULL),
                stderr=subprocess.PIPE,
                timeout=60,
                check=False,
                **options,
            )
            if result.returncode:
                raise ValueError(
                    "E_PORTABLE_DATABASE_FIXTURE_"
                    + name.upper()
                    + ": "
                    + result.stderr.decode("utf-8", errors="replace")[:1500]
                )
            return result.stdout

        data = root / "postgres"
        command(
            "initdb",
            [
                "-D",
                str(data),
                "-A",
                "trust",
                "-U",
                "fixture",
                "--no-locale",
                "-E",
                "UTF8",
            ],
            stdout=subprocess.PIPE,
        )
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        options = "-h 127.0.0.1 -p " + str(port)
        if os.name == "posix":
            options += " -k " + str(root)
        started = False
        try:
            command(
                "pg_ctl",
                [
                    "-D",
                    str(data),
                    "-l",
                    str(root / "postgres.log"),
                    "-w",
                    "start",
                    "-o",
                    options,
                ],
                stdout=subprocess.PIPE,
            )
            started = True

            def query(database, sql, **stream):
                return command(
                    "psql",
                    [
                        "-X",
                        "-h",
                        "127.0.0.1",
                        "-p",
                        str(port),
                        "-U",
                        "fixture",
                        "-d",
                        database,
                        "-v",
                        "ON_ERROR_STOP=1",
                        "-Atc",
                        sql,
                    ],
                    **stream,
                )

            for database in ("source", "target"):
                query("postgres", "CREATE DATABASE " + database, stdout=subprocess.PIPE)
                query(database, SCHEMA, stdout=subprocess.PIPE)
            payload = "synthetic SQL-looking text: '); COPY parent TO PROGRAM 'false'; --\\n\\! false\nGrüsse"
            query(
                "source",
                "INSERT INTO parent(payload,binary_data) VALUES(convert_from(decode('"
                + payload.encode("utf-8").hex()
                + "','hex'),'UTF8'),decode('"
                + bytes(range(256)).hex()
                + "','hex')); INSERT INTO child VALUES(1,1,2); SELECT setval('parent_id_seq',40,true)",
                stdout=subprocess.PIPE,
            )

            def export(sql, path):
                if os.name == "nt":
                    with path.open("xb"):
                        pass
                    query(
                        "source",
                        portable.file_copy_command(sql, path),
                        stdout=subprocess.PIPE,
                    )
                else:
                    with path.open("xb") as stream:
                        query("source", sql, stdout=stream)

            snapshot, files = portable.capture(
                lambda sql: query("source", sql, stdout=subprocess.PIPE),
                export,
                root / "rows'quoted",
            )

            def restore():
                def copy_in(sql, path):
                    if os.name == "nt":
                        query(
                            "target",
                            portable.file_copy_command(sql, path),
                            stdout=subprocess.PIPE,
                        )
                    else:
                        with path.open("rb") as stream:
                            query("target", sql, stdin=stream, stdout=subprocess.PIPE)

                portable.restore(
                    lambda sql: query("target", sql, stdout=subprocess.PIPE),
                    lambda sql: query("target", sql, stdout=subprocess.PIPE),
                    copy_in,
                    snapshot,
                    files,
                )

            restore()
            restore()
            actual = json.loads(
                query(
                    "target",
                    "SELECT to_json(payload) FROM parent",
                    stdout=subprocess.PIPE,
                )
            )
            if (
                actual != payload
                or query(
                    "target", "SELECT nextval('parent_id_seq')", stdout=subprocess.PIPE
                ).strip()
                != b"41"
            ):
                raise ValueError("E_PORTABLE_DATABASE_FIXTURE_CONTENT")
            if (
                query(
                    "target",
                    "SELECT encode(binary_data,'hex') FROM parent",
                    stdout=subprocess.PIPE,
                )
                .strip()
                .decode()
                != bytes(range(256)).hex()
            ):
                raise ValueError("E_PORTABLE_DATABASE_FIXTURE_BINARY_BYTES")
            # A real invalid FK must fail even though binary loading temporarily
            # suppressed FK triggers. No application is activated on failure.
            query(
                "source",
                "SET session_replication_role=replica; UPDATE child SET parent_id=999",
                stdout=subprocess.PIPE,
            )
            invalid, invalid_files = portable.capture(
                lambda sql: query("source", sql, stdout=subprocess.PIPE),
                export,
                root / "invalid-rows",
            )

            def invalid_copy(sql, path):
                if os.name == "nt":
                    query(
                        "target",
                        portable.file_copy_command(sql, path),
                        stdout=subprocess.PIPE,
                    )
                else:
                    with path.open("rb") as stream:
                        query("target", sql, stdin=stream, stdout=subprocess.PIPE)

            try:
                portable.restore(
                    lambda sql: query("target", sql, stdout=subprocess.PIPE),
                    lambda sql: query("target", sql, stdout=subprocess.PIPE),
                    invalid_copy,
                    invalid,
                    invalid_files,
                )
            except ValueError:
                pass
            else:
                raise ValueError("E_PORTABLE_DATABASE_FIXTURE_FK_ACCEPTED")
            return {
                "actualPostgreSQL": True,
                "binaryCopyRoundtrip": True,
                "sqlLookingDataPreserved": True,
                "repeatImport": True,
                "sequencePositionPreserved": True,
                "allBinaryByteValuesPreserved": True,
                "invalidForeignKeyRejected": True,
                "archivedSqlExecuted": False,
                "applicationRestoreVerified": False,
            }
        finally:
            if started:
                command(
                    "pg_ctl",
                    ["-D", str(data), "-m", "immediate", "-w", "stop"],
                    stdout=subprocess.PIPE,
                )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--postgres-bin", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = exercise(args.postgres_bin.resolve())
    args.report.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
