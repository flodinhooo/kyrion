import importlib.util
import zipfile
import zlib
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "verify_runtime", Path(__file__).with_name("Verify-CoreRuntime.py")
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.mark.parametrize(
    "failure", [None, "checksum", "missing", "pending", "lease", "failed"]
)
def test_read_only_gate_rejects_mismatches_new_migrations_and_active_leases(
    tmp_path, monkeypatch, failure
):
    sql = "CREATE TABLE test(id INT);\r\n-- retained\r\n"
    crc = zlib.crc32("".join(sql.splitlines()).encode())
    checksum = crc if crc < 2**31 else crc - 2**32
    artifact = tmp_path / "runtime.jar"
    with zipfile.ZipFile(artifact, "w") as archive:
        if failure != "missing":
            archive.writestr(
                "BOOT-INF/classes/db/migration/V1__test.sql", "\ufeff" + sql
            )
        if failure == "pending":
            archive.writestr("BOOT-INF/classes/db/migration/V2__new.sql", "SELECT 1;")

    def query(statement):
        if "flyway_schema_history" in statement:
            return f"1|{checksum + (failure == 'checksum')}|{'f' if failure == 'failed' else 't'}"
        assert statement.startswith("SELECT count(*) FROM calendar_sync_schedule")
        return "1" if failure == "lease" else "0"

    monkeypatch.setattr(module, "query", query)
    summary = module.verify(artifact)
    assert summary["safe"] is (failure is None)


@pytest.mark.parametrize("installed", [[39], [39, 40]])
def test_v39_and_v40_artifacts_cannot_cross_the_rollout_boundary(
    tmp_path, monkeypatch, installed
):
    artifact = tmp_path / "runtime.jar"
    version = 40 if installed == [39] else 39
    checksum = zlib.crc32(b"SELECT 1;")
    with zipfile.ZipFile(artifact, "w") as archive:
        for migration in range(39, version + 1):
            archive.writestr(
                f"BOOT-INF/classes/db/migration/V{migration}__synthetic.sql",
                "SELECT 1;",
            )

    def query(statement):
        if "flyway_schema_history" in statement:
            return "\n".join(f"{migration}|{checksum}|t" for migration in installed)
        return "0"

    monkeypatch.setattr(module, "query", query)
    assert module.verify(artifact)["safe"] is False
