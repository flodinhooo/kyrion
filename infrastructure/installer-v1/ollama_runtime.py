"""Explicit local runtime selection; no inference/configuration is implied."""

from __future__ import annotations

import hashlib
import http.client
import json
import re
import socket
import time
from pathlib import Path

from authority import require_active
from bundle import unique_object
from local_listeners import loopback_bindings
from recovery import load_installation
from runtime import installation_lock

LIMIT = 1024**2
REQUEST_SECONDS = 15
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}\Z")
DIGEST = re.compile(r"(?:sha256:)?[a-f0-9]{64}\Z")
VERSION = re.compile(r"\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]{1,60})?\Z")


class DeadlineSocket(socket.socket):
    """SocketIO's buffered header/body reads share one absolute deadline."""

    deadline: float

    def recv_into(self, buffer, nbytes=0, flags=0):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError()
        self.settimeout(min(5, remaining))
        return super().recv_into(buffer, nbytes, flags)


def document(port: int, route: str) -> dict:
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError("E_OLLAMA_ENDPOINT")
    if route not in {"/api/version", "/api/tags", "/api/ps"}:
        raise ValueError("E_OLLAMA_PROTOCOL")
    client = http.client.HTTPConnection(
        "127.0.0.1", port, timeout=min(5, REQUEST_SECONDS)
    )
    deadline = time.monotonic() + REQUEST_SECONDS
    try:
        client.connect()
        connected = client.sock
        client.sock = DeadlineSocket(
            connected.family, connected.type, connected.proto, fileno=connected.detach()
        )
        client.sock.deadline = deadline
        client.sock.settimeout(min(5, max(0.001, deadline - time.monotonic())))
        client.request("GET", route, headers={"Accept": "application/json"})
        response = client.getresponse()
        if response.status != 200 or response.getheader("Content-Encoding") not in (
            None,
            "identity",
        ):
            raise ValueError("E_OLLAMA_PROTOCOL")
        raw = response.read(LIMIT + 1)
        if len(raw) > LIMIT:
            raise ValueError("E_OLLAMA_PROTOCOL")
        result = json.loads(raw, object_pairs_hook=unique_object)
        if not isinstance(result, dict) or "error" in result:
            raise ValueError("E_OLLAMA_PROTOCOL")
        return result
    except (
        OSError,
        http.client.HTTPException,
        ValueError,
        UnicodeError,
        RecursionError,
    ):
        raise ValueError("E_OLLAMA_PROTOCOL") from None
    finally:
        client.close()


def model_rows(value: dict, *, running=False) -> list[dict]:
    models = value.get("models")
    if not isinstance(models, list) or len(models) > 1000:
        raise ValueError("E_OLLAMA_PROTOCOL")
    result, names = [], set()
    for row in models:
        if not isinstance(row, dict):
            raise ValueError("E_OLLAMA_PROTOCOL")  # noqa: TRY004 -- stable boundary code
        name, digest, size = row.get("name"), row.get("digest"), row.get("size")
        if (
            not isinstance(name, str)
            or not NAME.fullmatch(name)
            or name in names
            or not isinstance(digest, str)
            or not DIGEST.fullmatch(digest)
            or type(size) is not int
            or not 0 <= size <= 4 * 1024**4
        ):
            raise ValueError("E_OLLAMA_PROTOCOL")
        names.add(name)
        selected = {
            "name": name,
            "digest": digest.removeprefix("sha256:"),
            "bytes": size,
        }
        if running:
            vram = row.get("size_vram")
            if vram is not None and (
                type(vram) is not int or not 0 <= vram <= 4 * 1024**4
            ):
                raise ValueError("E_OLLAMA_PROTOCOL")
            selected["vramBytesObserved"] = vram
        result.append(selected)
    return sorted(result, key=lambda row: row["name"])


def probe(port: int = 11434) -> dict:
    bindings = loopback_bindings(port)
    version = document(port, "/api/version").get("version")
    if (
        not isinstance(version, str)
        or len(version) > 100
        or not VERSION.fullmatch(version)
    ):
        raise ValueError("E_OLLAMA_PROTOCOL")
    models = model_rows(document(port, "/api/tags"))
    running = model_rows(document(port, "/api/ps"), running=True)
    if loopback_bindings(port) != bindings:
        raise ValueError("E_OLLAMA_CHANGED")
    return {
        "endpoint": f"http://127.0.0.1:{port}",
        "port": port,
        "version": version,
        "bindings": list(bindings),
        "models": models,
        "runningModels": running,
        "connectionTested": True,
        "processIdentityAuthenticated": False,
        "usableAcceleration": None,
        "benchmarkMeasured": False,
        "aiServiceConnected": False,
        "cloudEnabledByInstaller": False,
        "externalRuntimeCloudStatus": "unknown",
    }


def detected_version(port: int = 11434) -> str | None:
    """Inventory may read only version, never personal model names or inference."""
    try:
        before = loopback_bindings(port)
        version = document(port, "/api/version").get("version")
        if (
            not isinstance(version, str)
            or len(version) > 100
            or not VERSION.fullmatch(version)
        ):
            return None
        return version if loopback_bindings(port) == before else None
    except ValueError:
        return None


def selection_snapshot(observed: dict) -> str:
    # Running models/VRAM can change naturally; selection binds catalog/version/scope.
    selected = {
        key: observed[key]
        for key in ("endpoint", "port", "version", "bindings", "models")
    }
    return hashlib.sha256(
        json.dumps(selected, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def select(target: Path, port: int, *, review) -> dict:
    from operational_restore import require_admin
    from update_worker import validate_host

    require_admin()
    validate_host(target)
    with installation_lock(target):
        installation = load_installation(target)
        require_active(installation.state)
        installation.verify_files()
        previous = selection(installation.state)
        observed = probe(port)
        summary = {
            **observed,
            "previousSelection": previous,
            "externalRuntimeManaged": False,
            "configurationChanged": False,
            "modelDownloadsStarted": False,
        }
        if not review(summary):
            raise ValueError("E_OLLAMA_CANCELLED")
        current = probe(port)
        if selection_snapshot(current) != selection_snapshot(observed):
            raise ValueError("E_OLLAMA_CHANGED")
        selected = {
            "formatVersion": 1,
            "endpoint": current["endpoint"],
            "port": port,
            "externalRuntimeManaged": False,
            "selectedAt": int(time.time()),
            "observedVersion": current["version"],
            "snapshotSha256": selection_snapshot(current),
            "aiServiceConnected": False,
        }
        installation.state["ollamaRuntime"] = selected
        installation.save()
        return {"runtimeSelected": True, "selection": selected, "observation": current}


def selection(state: dict) -> dict | None:
    saved = state.get("ollamaRuntime")
    if saved is None:
        return None
    if (
        not isinstance(saved, dict)
        or set(saved)
        != {
            "formatVersion",
            "endpoint",
            "port",
            "externalRuntimeManaged",
            "selectedAt",
            "observedVersion",
            "snapshotSha256",
            "aiServiceConnected",
        }
        or type(saved["formatVersion"]) is not int
        or saved["formatVersion"] != 1
        or type(saved["port"]) is not int
        or not 1024 <= saved["port"] <= 65535
        or saved["endpoint"] != f"http://127.0.0.1:{saved['port']}"
        or saved["externalRuntimeManaged"] is not False
        or saved["aiServiceConnected"] is not False
        or type(saved["selectedAt"]) is not int
        or saved["selectedAt"] < 0
        or not isinstance(saved["observedVersion"], str)
        or len(saved["observedVersion"]) > 100
        or not VERSION.fullmatch(saved["observedVersion"])
        or not isinstance(saved["snapshotSha256"], str)
        or not re.fullmatch(r"[a-f0-9]{64}", saved["snapshotSha256"])
    ):
        raise ValueError("E_OLLAMA_SELECTION")
    return saved.copy()


def status(target: Path, port: int | None = None) -> dict:
    from operational_restore import require_admin
    from update_worker import validate_host

    require_admin()
    validate_host(target)
    with installation_lock(target):
        installation = load_installation(target)
        require_active(installation.state)
        installation.verify_files()
        saved = selection(installation.state)
        if saved is not None and port is not None and port != saved["port"]:
            raise ValueError("E_OLLAMA_ENDPOINT")
        port = port if port is not None else (saved["port"] if saved else 11434)
        try:
            observed = {"available": True, **probe(port)}
        except ValueError as error:
            code = str(error)
            observed = {
                "available": False,
                "probeAttempted": True,
                "error": code
                if code
                in {
                    "E_OLLAMA_PROTOCOL",
                    "E_OLLAMA_BINDING",
                    "E_OLLAMA_ENDPOINT",
                    "E_OLLAMA_CHANGED",
                }
                else "E_OLLAMA_PROTOCOL",
            }
        return {
            "runtimeSelected": saved is not None,
            "selection": saved,
            "observation": observed,
            "selectionMatchesCurrent": bool(
                saved is not None
                and observed.get("available") is True
                and saved["snapshotSha256"] == selection_snapshot(observed)
            ),
            "aiServiceConnected": False,
        }
