"""Disposable native PostgreSQL process; never register a system service."""

import os
import socket
import subprocess
import tempfile
from pathlib import Path


class PostgresFixture:
    def __init__(self, binaries: Path):
        if os.name == "posix" and os.geteuid() == 0:
            raise ValueError("E_FIXTURE_UNPRIVILEGED_REQUIRED")
        self.binaries = binaries
        self.temporary = tempfile.TemporaryDirectory(prefix="kyrion-restore-db-")
        self.root = Path(self.temporary.name)
        self.data = self.root / "postgres"
        self.environment = {
            key: value
            for key, value in os.environ.items()
            if key.upper() in {"SYSTEMROOT", "WINDIR", "PATH", "LANG", "LC_ALL"}
        }
        self.environment.update(
            HOME=str(self.root),
            USERPROFILE=str(self.root),
            APPDATA=str(self.root),
            TEMP=str(self.root),
            TMP=str(self.root),
            PGCLIENTENCODING="UTF8",
            PGCONNECT_TIMEOUT="5",
        )
        self.started = False

    def run(self, tool, arguments):
        executable = self.binaries / (tool + (".exe" if os.name == "nt" else ""))
        with (self.root / "control.log").open("ab") as log:
            result = subprocess.run(
                [str(executable), *arguments],
                cwd=self.root,
                env=self.environment,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                timeout=90,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        if result.returncode:
            raise ValueError("E_RESTORE_FIXTURE_" + tool.upper())

    def __enter__(self):
        try:
            self.run(
                "initdb",
                [
                    "-D",
                    str(self.data),
                    "-A",
                    "trust",
                    "-U",
                    "fixture",
                    "--no-locale",
                    "-E",
                    "UTF8",
                ],
            )
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
                self.port = probe.getsockname()[1]
            options = "-h 127.0.0.1 -p " + str(self.port)
            if os.name == "posix":
                options += " -k " + str(self.root)
            # Mark intent before start; a timeout after server startup still
            # receives scoped pg_ctl cleanup in __exit__.
            self.started = True
            self.run(
                "pg_ctl",
                [
                    "-D",
                    str(self.data),
                    "-l",
                    str(self.root / "postgres.log"),
                    "-w",
                    "start",
                    "-o",
                    options,
                ],
            )
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def query(self, database, sql, *, stdin=None, stdout=subprocess.PIPE):
        binary = self.binaries / ("psql.exe" if os.name == "nt" else "psql")
        result = subprocess.run(
            [
                str(binary),
                "-X",
                "-h",
                "127.0.0.1",
                "-p",
                str(self.port),
                "-U",
                "fixture",
                "-d",
                database,
                "-v",
                "ON_ERROR_STOP=1",
                "-Atc",
                sql,
            ],
            cwd=self.root,
            env=self.environment,
            stdin=stdin if stdin is not None else subprocess.DEVNULL,
            stdout=stdout,
            stderr=subprocess.PIPE,
            timeout=120,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if result.returncode:
            raise ValueError("E_RESTORE_FIXTURE_SQL: " + result.stderr.decode("utf-8", errors="replace").splitlines()[0])
        return result.stdout

    def __exit__(self, *_):
        try:
            if self.started:
                self.run(
                    "pg_ctl", ["-D", str(self.data), "-m", "immediate", "-w", "stop"]
                )
        finally:
            self.temporary.cleanup()
