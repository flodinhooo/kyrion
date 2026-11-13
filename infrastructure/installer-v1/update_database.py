"""Owned PostgreSQL template snapshots; never execute archived database code."""

from __future__ import annotations

import json
import re
import uuid

from portable_database import SCHEMA_SQL, descriptor
from recovery import COUNTS_SQL


def identity(platform) -> dict[str, str]:
    """Compare stable identity membership without persisting account information."""

    def digest(table: str, expression: str) -> str:
        return (
            platform.query(
                "SELECT encode(sha256(convert_to(coalesce(string_agg("
                + expression
                + ",',' ORDER BY "
                + expression
                + "),''),'UTF8')),'hex') FROM "
                + table
            )
            .decode()
            .strip()
        )

    return {
        "host": platform.query("SELECT id::text FROM installation_identity")
        .decode()
        .strip(),
        "users": digest("user_account", "id::text"),
        "spaces": digest("kyrion_space", "id::text"),
        "links": digest(
            "central_identity_link", "user_id::text||':'||issuer||':'||subject"
        ),
    }


def names(transaction: dict) -> dict[str, str]:
    identifier = uuid.UUID(transaction["id"]).hex
    return {
        "snapshot": "kyrion_pre_" + identifier,
        "failed": "kyrion_failed_" + identifier,
        "recovery": "kyrion_recovery_" + identifier,
    }


def sql_name(value: str) -> str:
    if value != "kyrion" and not re.fullmatch(
        r"kyrion_(?:pre|failed|recovery)_[a-f0-9]{32}", value
    ):
        raise ValueError("E_UPDATE_DATABASE_NAME")
    return '"' + value + '"'


def exists(platform, name: str) -> bool:
    sql_name(name)
    return (
        platform.query(
            "SELECT count(*) FROM pg_database WHERE datname='" + name + "'",
            database="postgres",
        ).strip()
        == b"1"
    )


def marker(platform, name: str) -> str:
    sql_name(name)
    return (
        platform.query(
            "SELECT coalesce(shobj_description(oid,'pg_database'),'') FROM pg_database WHERE datname='"
            + name
            + "'",
            database="postgres",
        )
        .decode()
        .strip()
    )


def mark(platform, name: str, identifier: str, kind: str) -> None:
    identifier = str(uuid.UUID(identifier))
    if kind not in {"snapshot", "recovery"}:
        raise ValueError("E_UPDATE_DATABASE_NAME")
    platform.query(
        "COMMENT ON DATABASE "
        + sql_name(name)
        + " IS 'kyrion-update:"
        + identifier
        + ":"
        + kind
        + "'",
        database="postgres",
    )


def terminate(platform, name: str) -> None:
    sql_name(name)
    platform.query(
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='"
        + name
        + "' AND pid<>pg_backend_pid()",
        database="postgres",
    )


def snapshot(platform, installation, metadata: dict) -> None:
    value = installation.state["updateTransaction"]
    name = names(value)["snapshot"]
    expected_marker = "kyrion-update:" + value["id"] + ":snapshot"
    if not exists(platform, name):
        value["snapshotIntent"] = True
        installation.save()
        terminate(platform, "kyrion")
        platform.query(
            "CREATE DATABASE " + sql_name(name) + " TEMPLATE kyrion",
            database="postgres",
        )
    elif value.get("snapshotIntent") is not True:
        raise ValueError("E_UPDATE_DATABASE_FOREIGN")
    current = marker(platform, name)
    if current not in {"", expected_marker}:
        raise ValueError("E_UPDATE_DATABASE_FOREIGN")
    if not current:
        schema = descriptor(platform.query(SCHEMA_SQL, database=name))
        if (
            schema != metadata["portableDatabase"]["schema"]
            or json.loads(platform.query(COUNTS_SQL, database=name))
            != metadata["verificationCounts"]
        ):
            raise ValueError("E_UPDATE_SNAPSHOT_CHANGED")
        mark(platform, name, value["id"], "snapshot")
    platform.query(
        "ALTER DATABASE " + sql_name(name) + " ALLOW_CONNECTIONS false",
        database="postgres",
    )


def recover(platform, installation, metadata: dict) -> None:
    """Keep failed data; clone a reserved immutable snapshot, then rename once."""
    value = installation.state["updateTransaction"]
    selected = names(value)
    expected = "kyrion-update:" + value["id"]
    if (
        not exists(platform, selected["snapshot"])
        or marker(platform, selected["snapshot"]) != expected + ":snapshot"
    ):
        raise ValueError("E_UPDATE_SNAPSHOT_MISSING")
    if (
        exists(platform, "kyrion")
        and marker(platform, "kyrion") == expected + ":recovery"
    ):
        lock_failed(platform, value, selected["failed"])
        return
    copy = selected["recovery"]
    if not exists(platform, copy):
        value["recoveryCloneIntent"] = True
        installation.save()
        platform.query(
            "CREATE DATABASE "
            + sql_name(copy)
            + " TEMPLATE "
            + sql_name(selected["snapshot"]),
            database="postgres",
        )
    elif value.get("recoveryCloneIntent") is not True:
        raise ValueError("E_UPDATE_DATABASE_FOREIGN")
    if marker(platform, copy) not in {"", expected + ":recovery"}:
        raise ValueError("E_UPDATE_DATABASE_FOREIGN")
    if (
        descriptor(platform.query(SCHEMA_SQL, database=copy))
        != metadata["portableDatabase"]["schema"]
        or json.loads(platform.query(COUNTS_SQL, database=copy))
        != metadata["verificationCounts"]
    ):
        raise ValueError("E_UPDATE_SNAPSHOT_CHANGED")
    platform.verify_snapshot_rows(copy, metadata)
    mark(platform, copy, value["id"], "recovery")
    terminate(platform, copy)
    if exists(platform, "kyrion"):
        if exists(platform, selected["failed"]):
            raise ValueError("E_UPDATE_DATABASE_FOREIGN")
        value["databaseRenameIntent"] = True
        installation.save()
        terminate(platform, "kyrion")
        platform.query(
            "ALTER DATABASE kyrion RENAME TO " + sql_name(selected["failed"]),
            database="postgres",
        )
    lock_failed(platform, value, selected["failed"])
    platform.query(
        "ALTER DATABASE " + sql_name(copy) + " RENAME TO kyrion", database="postgres"
    )


def lock_failed(platform, value: dict, name: str) -> None:
    """Reassert isolation even when interruption followed the database rename."""
    if value.get("databaseRenameIntent") is not True or not exists(platform, name):
        raise ValueError("E_UPDATE_DATABASE_FOREIGN")
    terminate(platform, name)
    platform.query(
        "ALTER DATABASE " + sql_name(name) + " ALLOW_CONNECTIONS false",
        database="postgres",
    )
