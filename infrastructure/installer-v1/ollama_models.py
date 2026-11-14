"""Reviewed model mutations on an explicitly selected loopback runtime."""

from __future__ import annotations

import hashlib
import http.client
import json
import re
import time
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from typing import Literal, NotRequired, TypedDict

from authority import require_active
from bundle import unique_object
from local_listeners import loopback_bindings
from model_cache import cached_catalog
from ollama_runtime import NAME, DeadlineSocket, probe, selection, selection_snapshot
from recovery import load_installation
from release_policy import fetch_document
from runtime import installation_lock

OPERATION_SECONDS = 1800
LINE_LIMIT = 16384
STREAM_LIMIT = 32 * 1024**2


class ModelProgress(TypedDict):
    phase: Literal[
        "running", "downloading", "verifying", "publishing", "runtime-finished"
    ]
    totalBytes: NotRequired[int]
    completedBytes: NotRequired[int]


Progress = Callable[[ModelProgress], None]
Review = Callable[[dict], bool]


def progress_record(value: object) -> ModelProgress:
    if not isinstance(value, dict) or "error" in value:
        raise ValueError("E_OLLAMA_MODEL_PROTOCOL")
    status = value.get("status")
    if not isinstance(status, str) or not 1 <= len(status) <= 500:
        raise ValueError("E_OLLAMA_MODEL_PROTOCOL")
    phase: Literal[
        "running", "downloading", "verifying", "publishing", "runtime-finished"
    ] = "running"
    if status.startswith("pulling "):
        phase = "downloading"
    elif status == "verifying sha256 digest":
        phase = "verifying"
    elif status == "writing manifest":
        phase = "publishing"
    elif status == "success":
        phase = "runtime-finished"
    result: ModelProgress = {"phase": phase}
    for name in ("total", "completed"):
        if name in value:
            number = value[name]
            if type(number) is not int or not 0 <= number <= 1024**4:
                raise ValueError("E_OLLAMA_MODEL_PROTOCOL")
            if name == "total":
                result["totalBytes"] = number
            else:
                result["completedBytes"] = number
    if value.get("completed", 0) > value.get("total", 1024**4):
        raise ValueError("E_OLLAMA_MODEL_PROTOCOL")
    if "digest" in value and (
        not isinstance(value["digest"], str)
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", value["digest"])
    ):
        raise ValueError("E_OLLAMA_MODEL_PROTOCOL")
    return result


def mutate(port: int, action: str, model: str, progress: Progress) -> None:
    if (
        type(port) is not int
        or not 1024 <= port <= 65535
        or action not in {"pull", "remove"}
    ):
        raise ValueError("E_OLLAMA_ENDPOINT")
    if (
        not isinstance(model, str)
        or not NAME.fullmatch(model)
        or any(part in {"", ".", ".."} for part in model.split("/"))
    ):
        raise ValueError("E_OLLAMA_MODEL_NAME")
    bindings = loopback_bindings(port)
    client = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    response = None
    try:
        client.connect()
        connected = client.sock
        client.sock = DeadlineSocket(
            connected.family, connected.type, connected.proto, fileno=connected.detach()
        )
        client.sock.deadline = time.monotonic() + OPERATION_SECONDS
        client.sock.settimeout(5)
        body = {"model": model}
        if action == "pull":
            body.update(stream=True, insecure=False)
        client.request(
            "POST" if action == "pull" else "DELETE",
            "/api/pull" if action == "pull" else "/api/delete",
            body=json.dumps(body).encode(),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/x-ndjson, application/json",
            },
        )
        response = client.getresponse()
        if response.status != 200 or response.getheader("Content-Encoding") not in {
            None,
            "identity",
        }:
            raise ValueError("E_OLLAMA_MODEL_PROTOCOL")
        if action == "remove":
            raw = response.read(LINE_LIMIT + 1)
            if len(raw) > LINE_LIMIT:
                raise ValueError("E_OLLAMA_MODEL_PROTOCOL")
            if raw.strip():
                value = json.loads(raw, object_pairs_hook=unique_object)
                if not isinstance(value, dict) or "error" in value:
                    raise ValueError("E_OLLAMA_MODEL_PROTOCOL")
        else:
            transferred, complete = 0, False
            while True:
                line = response.readline(LINE_LIMIT + 1)
                if not line:
                    break
                transferred += len(line)
                if len(line) > LINE_LIMIT or transferred > STREAM_LIMIT or complete:
                    raise ValueError("E_OLLAMA_MODEL_PROTOCOL")
                value = json.loads(line, object_pairs_hook=unique_object)
                record = progress_record(value)
                progress(record)
                complete = record["phase"] == "runtime-finished"
            if not complete:
                raise ValueError("E_OLLAMA_MODEL_INTERRUPTED")
        if loopback_bindings(port) != bindings:
            raise ValueError("E_OLLAMA_CHANGED")
    except (OSError, http.client.HTTPException):
        raise ValueError("E_OLLAMA_MODEL_INTERRUPTED") from None
    except (ValueError, UnicodeError, RecursionError) as error:
        if re.fullmatch(r"E_OLLAMA_[A-Z_]{1,60}", str(error)):
            raise
        raise ValueError("E_OLLAMA_MODEL_PROTOCOL") from None
    finally:
        if response is not None:
            response.close()
        client.close()


def registry_manifest(model: dict) -> None:
    name, tag = model["id"].split(":")
    if (
        model["registryUrl"]
        != "https://registry.ollama.ai/v2/library/" + name + "/manifests/" + tag
    ):
        raise ValueError("E_OLLAMA_MODEL_SOURCE")
    try:
        raw = fetch_document(model["registryUrl"])
    except (OSError, ValueError):
        raise ValueError("E_OLLAMA_MODEL_SOURCE") from None
    if hashlib.sha256(raw).hexdigest() != model["manifestSha256"]:
        raise ValueError("E_OLLAMA_MODEL_SOURCE")
    value = json.loads(raw, object_pairs_hook=unique_object)
    if (
        not isinstance(value, dict)
        or value.get("schemaVersion") != 2
        or not isinstance(value.get("layers"), list)
        or not 1 <= len(value["layers"]) <= 100
    ):
        raise ValueError("E_OLLAMA_MODEL_SOURCE")
    rows = [value.get("config"), *value["layers"]]
    for row in rows:
        if (
            not isinstance(row, dict)
            or type(row.get("size")) is not int
            or not 0 <= row["size"] <= 1024**4
            or not isinstance(row.get("digest"), str)
            or not re.fullmatch(r"sha256:[a-f0-9]{64}", row["digest"])
        ):
            raise ValueError("E_OLLAMA_MODEL_SOURCE")
    if sum(row["size"] for row in rows) != model["downloadBytes"]:
        raise ValueError("E_OLLAMA_MODEL_SOURCE")


@contextmanager
def opened(target: Path, port: int | None):
    from operational_restore import require_admin
    from update_worker import validate_host

    require_admin()
    validate_host(target)
    with installation_lock(target):
        installation = load_installation(target)
        require_active(installation.state)
        installation.verify_files()
        pending(installation.state)
        saved = selection(installation.state)
        if saved is None:
            raise ValueError("E_OLLAMA_SELECTION")
        if port is not None and port != saved["port"]:
            raise ValueError("E_OLLAMA_ENDPOINT")
        yield installation, saved


def target_model(observed, model):
    return next((row for row in observed["models"] if row["name"] == model), None)


def pending(state: dict) -> dict | None:
    job = state.get("ollamaModelOperation")
    if job is None:
        return None
    if not isinstance(job, dict) or set(job) != {
        "action",
        "model",
        "digest",
        "beforeSnapshotSha256",
        "originalModel",
        "phase",
        "startedAt",
        "error",
    }:
        raise ValueError("E_OLLAMA_MODEL_JOURNAL")
    if (
        job["action"] not in {"pull", "remove"}
        or job["phase"] not in {"running", "interrupted", "complete"}
        or not isinstance(job["model"], str)
        or not NAME.fullmatch(job["model"])
        or type(job["startedAt"]) is not int
        or job["startedAt"] < 0
    ):
        raise ValueError("E_OLLAMA_MODEL_JOURNAL")
    for key in ("digest", "beforeSnapshotSha256"):
        if not isinstance(job[key], str) or not re.fullmatch(r"[0-9a-f]{64}", job[key]):
            raise ValueError("E_OLLAMA_MODEL_JOURNAL")
    original = job["originalModel"]
    if original is not None and (
        not isinstance(original, dict)
        or set(original) != {"name", "digest", "bytes"}
        or original["name"] != job["model"]
        or original["digest"] != job["digest"]
        or type(original["bytes"]) is not int
        or not 0 <= original["bytes"] <= 4 * 1024**4
    ):
        raise ValueError("E_OLLAMA_MODEL_JOURNAL")
    if job["error"] is not None and (
        not isinstance(job["error"], str)
        or not re.fullmatch(r"E_[A-Z_]{1,70}", job["error"])
    ):
        raise ValueError("E_OLLAMA_MODEL_JOURNAL")
    return job


def observe(installation, saved):
    current = probe(saved["port"])
    if selection_snapshot(current) == saved["snapshotSha256"]:
        return current
    job = pending(installation.state)
    if (
        job is None
        or job["phase"] == "complete"
        or job["beforeSnapshotSha256"] != saved["snapshotSha256"]
    ):
        raise ValueError("E_OLLAMA_CHANGED")
    row = target_model(current, job["model"])
    if (
        job["action"] == "pull" and (row is None or row["digest"] != job["digest"])
    ) or (job["action"] == "remove" and row is not None):
        raise ValueError("E_OLLAMA_CHANGED")
    before_models = [row for row in current["models"] if row["name"] != job["model"]]
    if job["originalModel"] is not None:
        before_models.append(job["originalModel"])
    before = {**current, "models": sorted(before_models, key=lambda row: row["name"])}
    if selection_snapshot(before) != saved["snapshotSha256"]:
        raise ValueError("E_OLLAMA_CHANGED")
    return current


def execute(
    installation, saved, action, model, digest, before, review, summary, progress
):
    if not review(summary):
        raise ValueError("E_OLLAMA_CANCELLED")
    current = probe(saved["port"])
    if selection_snapshot(current) != selection_snapshot(before):
        raise ValueError("E_OLLAMA_CHANGED")
    if action == "remove" and any(
        row["name"] == model or row["digest"] == digest
        for row in current["runningModels"]
    ):
        raise ValueError("E_OLLAMA_MODEL_IN_USE")
    original = target_model(current, model)
    job = {
        "action": action,
        "model": model,
        "digest": digest,
        "beforeSnapshotSha256": selection_snapshot(current),
        "originalModel": original,
        "phase": "running",
        "startedAt": int(time.time()),
        "error": None,
    }
    installation.state["ollamaModelOperation"] = job
    installation.save()
    try:
        if (action == "pull" and original is None) or (
            action == "remove" and original is not None
        ):
            mutate(saved["port"], action, model, progress)
        after = probe(saved["port"])
        row = target_model(after, model)
        if (action == "pull" and (row is None or row["digest"] != digest)) or (
            action == "remove" and row is not None
        ):
            raise ValueError("E_OLLAMA_MODEL_RESULT")
        reconstructed = {
            **after,
            "models": sorted(
                [item for item in after["models"] if item["name"] != model]
                + ([original] if original else []),
                key=lambda item: item["name"],
            ),
        }
        if selection_snapshot(reconstructed) != selection_snapshot(current):
            raise ValueError("E_OLLAMA_CHANGED")
        saved["snapshotSha256"] = selection_snapshot(after)
        installation.state["ollamaRuntime"] = saved
        job["phase"] = "complete"
        installation.save()
    except (ValueError, OSError, KeyboardInterrupt) as error:
        code = str(error).split(":", 1)[0]
        job.update(
            phase="interrupted",
            error=code
            if re.fullmatch(r"E_[A-Z_]{1,70}", code)
            else "E_OLLAMA_MODEL_INTERRUPTED",
        )
        installation.save()
        raise
    return {
        "action": action,
        "model": model,
        "phase": "complete",
        "runtimeReportedAvailable": action == "pull",
        "manifestDigestMatchesCatalog": action == "pull",
        "independentBlobVerification": False,
        "aiServiceConnected": False,
        "cloudEnabledByInstaller": False,
    }


def pull(
    target: Path,
    model_id: str,
    *,
    port: int | None = None,
    review: Review,
    progress: Progress = lambda _record: None,
) -> dict:
    with opened(target, port) as (installation, saved):
        catalog = cached_catalog(installation)
        model = next((row for row in catalog["models"] if row["id"] == model_id), None)
        if model is None:
            raise ValueError("E_OLLAMA_MODEL_NAME")
        before = observe(installation, saved)
        existing = target_model(before, model_id)
        if existing is not None and existing["digest"] != model["manifestSha256"]:
            raise ValueError("E_OLLAMA_MODEL_CONFLICT")
        if existing is None:
            registry_manifest(model)
        return execute(
            installation,
            saved,
            "pull",
            model_id,
            model["manifestSha256"],
            before,
            review,
            {
                "model": model,
                "catalogSequence": catalog["sequence"],
                "catalogReviewedAt": catalog["reviewedAt"],
                "alreadyAvailable": existing is not None,
                "externalRuntimeManaged": False,
                "modelStoreCapacityBytes": None,
                "resourceRequirementsAreEstimates": True,
                "aiServiceConnected": False,
            },
            progress,
        )


def remove(
    target: Path, model_id: str, *, port: int | None = None, review: Review
) -> dict:
    with opened(target, port) as (installation, saved):
        before = observe(installation, saved)
        original = target_model(before, model_id)
        job = pending(installation.state)
        if original is None and not (
            job
            and job["action"] == "remove"
            and job["model"] == model_id
            and job["phase"] != "complete"
        ):
            raise ValueError("E_OLLAMA_MODEL_NAME")
        digest = original["digest"] if original else job["digest"]
        if any(
            row["name"] == model_id or row["digest"] == digest
            for row in before["runningModels"]
        ):
            raise ValueError("E_OLLAMA_MODEL_IN_USE")
        return execute(
            installation,
            saved,
            "remove",
            model_id,
            digest,
            before,
            review,
            {
                "model": original or {"name": model_id, "digest": digest},
                "alreadyAbsent": original is None,
                "externalRuntimeManaged": False,
                "otherApplicationsMayUseModel": True,
            },
            lambda _record: None,
        )
