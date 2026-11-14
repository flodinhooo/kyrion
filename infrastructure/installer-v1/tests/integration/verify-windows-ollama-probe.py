"""Run only a copied verified Ollama CLI in an empty owned developer fixture.

No installed instance, user model, generation, service or cloud inference is used.
An explicit flag enables a reviewed model download in this new empty fixture.
This is actual Windows runtime/TCP/API evidence, not installer/service acceptance.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from bundle import sha256
from host import reject_links
from local_listeners import windows_records
from ollama_runtime import probe, select
from windows_process import ContainedProcess
from windows_system import base_environment, system_directory


def exercise_models(root: Path, port: int) -> dict:
    import ollama_models
    from models import load_catalog
    from recovery import load_installation
    from runtime import Installation

    model = load_catalog()["models"][0]
    if (
        model["id"] != "qwen3:0.6b"
        or model["license"] != "Apache-2.0"
        or model["downloadBytes"] > 600 * 1024**2
    ):
        raise ValueError("E_TEST_MODEL_REVIEW_CHANGED")
    if shutil.disk_usage(root).free < model["downloadBytes"] * 3 + 2 * 1024**3:
        raise ValueError("E_TEST_MODEL_SPACE")
    print(
        json.dumps(
            {
                "scope": "isolated-developer-model-download-review",
                "model": model["id"],
                "downloadBytes": model["downloadBytes"],
                "license": model["license"],
                "licenseUrl": model["licenseUrl"],
                "inferenceRequested": False,
            }
        ),
        flush=True,
    )
    installation = Installation(
        root / "installer-state",
        {"release": "0.0.0-dev.ollama-model-fixture", "architecture": "windows/amd64"},
        "a" * 64,
        "fixture.test",
        "127.0.0.1",
    )
    stopped_at = []

    def interrupt(record):
        if record.get("completedBytes", 0) >= 8 * 1024**2:
            stopped_at.append(record["completedBytes"])
            raise KeyboardInterrupt()

    with (
        patch("operational_restore.require_admin"),
        patch("update_worker.validate_host"),
    ):
        # Only host installation/administrator authority is adapted for this
        # marked private process fixture. TCP, HTTP, catalog and journal are real.
        select(installation.target, port, review=lambda _summary: True)
        try:
            ollama_models.pull(
                installation.target,
                model["id"],
                review=lambda _summary: True,
                progress=interrupt,
            )
        except KeyboardInterrupt:
            if not stopped_at:
                raise
        else:
            raise ValueError("E_TEST_MODEL_INTERRUPTION_NOT_REACHED")
        if (
            load_installation(installation.target).state["ollamaModelOperation"][
                "phase"
            ]
            != "interrupted"
        ):
            raise ValueError("E_TEST_MODEL_INTERRUPTION_JOURNAL")
        partial_files = [
            path
            for path in (root / "models/blobs").glob("*-partial*")
            if path.is_file()
        ]
        (root / "model-interruption-evidence.json").write_text(
            json.dumps(
                {
                    "scope": "installer-ollama-development-fixture",
                    "interruptedAtReportedBytes": stopped_at[0],
                    "partialCacheObserved": bool(partial_files),
                    "interruptedJournalReloaded": True,
                }
            ),
            encoding="utf-8",
        )
        resumed = []
        result = ollama_models.pull(
            installation.target,
            model["id"],
            review=lambda _summary: True,
            progress=resumed.append,
        )
        if (
            result["independentBlobVerification"]
            or not result["runtimeReportedAvailable"]
        ):
            raise ValueError("E_TEST_MODEL_RECEIPT")
        # 0.40.16 keeps a legacy downgrade anchor with an extra manifest layer.
        # Verify runnable v2 bytes, or exact legacy bytes on older runtimes.
        # Never normalize away a hash mismatch or trust API output.
        manifest_paths = (
            root / "models/manifests-v2/ollama.com/library/qwen3/0.6b",
            root / "models/manifests/registry.ollama.ai/library/qwen3/0.6b",
        )
        verified_paths = []
        for path in manifest_paths:
            reject_links(path)
            if path.is_file() and sha256(path) == model["manifestSha256"]:
                verified_paths.append(path)
        if not verified_paths:
            raise ValueError("E_TEST_MODEL_MANIFEST")
        manifest_path = verified_paths[0]
        manifest = json.loads(manifest_path.read_bytes())
        for row in [manifest["config"], *manifest["layers"]]:
            path = root / "models/blobs" / row["digest"].replace(":", "-")
            reject_links(path)
            if path.stat().st_size != row["size"] or sha256(path) != row[
                "digest"
            ].removeprefix("sha256:"):
                raise ValueError("E_TEST_MODEL_BLOB")
        if probe(port)["runningModels"]:
            raise ValueError("E_TEST_MODEL_GENERATION_UNEXPECTED")
        removed = ollama_models.remove(
            installation.target, model["id"], review=lambda _summary: True
        )
        if (
            removed["runtimeReportedAvailable"]
            or probe(port)["models"]
            or any(path.exists() for path in manifest_paths)
        ):
            raise ValueError("E_TEST_MODEL_REMOVAL")
    return {
        "actualModelDownload": True,
        "model": model["id"],
        "downloadBytes": model["downloadBytes"],
        "interruptedAtReportedBytes": stopped_at[0],
        "actualPartialCacheObserved": bool(partial_files),
        "explicitRepeatAfterJournalReload": True,
        "firstResumedReportedBytes": next(
            (row["completedBytes"] for row in resumed if "completedBytes" in row), None
        ),
        "runtimeProcessRestarted": False,
        "fixtureIndependentManifestAndBlobHashesVerified": True,
        "actualSingleModelRemoval": True,
        "hostInstallationAuthorityInjected": True,
        "generationOrBenchmark": False,
    }


def exercise(
    executable: Path, expected: str, parent: Path, *, model_operations=False
) -> dict:
    if os.name != "nt":
        raise ValueError("E_TEST_PLATFORM")
    reject_links(executable)
    reject_links(parent)
    if not executable.is_file() or not parent.is_dir():
        raise ValueError("E_TEST_PATH")
    if hashlib.sha256(executable.read_bytes()).hexdigest() != expected:
        raise ValueError("E_TEST_HASH")
    signature = subprocess.run(
        [
            str(system_directory() / "WindowsPowerShell/v1.0/powershell.exe"),
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "$item=([Console]::In.ReadToEnd() | ConvertFrom-Json); $sig=Get-AuthenticodeSignature -LiteralPath $item.path; @{status=[int]$sig.Status; publisher=$sig.SignerCertificate.GetNameInfo([System.Security.Cryptography.X509Certificates.X509NameType]::SimpleName,$false)} | ConvertTo-Json -Compress",
        ],
        input=json.dumps({"path": str(executable)}).encode(),
        capture_output=True,
        timeout=45,
        check=True,
        env=base_environment(),
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    trust = json.loads(signature.stdout.decode("utf-8-sig"))
    if trust != {"status": 0, "publisher": "Ollama Inc."}:
        raise ValueError("E_TEST_PUBLISHER")
    root = parent / ("ollama-probe-" + uuid.uuid4().hex)
    root.mkdir(mode=0o700)
    # Throwaway identities inherit a protected current-user/SYSTEM DACL.
    # mkdir(mode=0700) alone is insufficient on Python 3.12 Windows.
    subprocess.run(
        [
            str(system_directory() / "WindowsPowerShell/v1.0/powershell.exe"),
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "$ErrorActionPreference='Stop'; $item=([Console]::In.ReadToEnd() | ConvertFrom-Json); $sid=[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value; $acl=New-Object System.Security.AccessControl.DirectorySecurity; $acl.SetSecurityDescriptorSddlForm(('D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;'+$sid+')'),[System.Security.AccessControl.AccessControlSections]::Access); $directory=Get-Item -LiteralPath $item.path; $directory.SetAccessControl($acl); $verified=$directory.GetAccessControl(); if (-not $verified.AreAccessRulesProtected) { throw 'E_TEST_FIXTURE_PERMISSIONS' }",
        ],
        input=json.dumps({"path": str(root)}).encode(),
        capture_output=True,
        timeout=30,
        check=True,
        env=base_environment(),
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    (root / "fixture.json").write_text(
        json.dumps(
            {"scope": "installer-ollama-development-fixture", "sourceSha256": expected}
        )
    )
    worker = root / "ollama.exe"
    shutil.copyfile(executable, worker)
    if hashlib.sha256(worker.read_bytes()).hexdigest() != expected:
        raise ValueError("E_TEST_HASH")
    for name in ("home", "models", "tmp", "appdata", "localappdata"):
        (root / name).mkdir(mode=0o700)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    environment = {
        **base_environment(),
        "HOME": str(root / "home"),
        "USERPROFILE": str(root / "home"),
        "APPDATA": str(root / "appdata"),
        "LOCALAPPDATA": str(root / "localappdata"),
        "TEMP": str(root / "tmp"),
        "TMP": str(root / "tmp"),
        "OLLAMA_MODELS": str(root / "models"),
        "OLLAMA_HOST": f"127.0.0.1:{port}",
        "OLLAMA_NO_CLOUD": "1",
    }
    observed = None
    with ContainedProcess(
        worker.absolute(), ["serve"], environment, root.absolute()
    ) as child:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetProcessId.argtypes = [ctypes.c_void_p]
        kernel.GetProcessId.restype = ctypes.c_uint32
        pid = kernel.GetProcessId(child.process)
        if not pid:
            raise ValueError("E_TEST_PROCESS")
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if child.poll() is not None:
                raise ValueError("E_TEST_RUNTIME_EXIT")
            bindings = [
                (address, owner)
                for address, found, owner in windows_records()
                if found == port
            ]
            if bindings:
                if bindings != [("127.0.0.1", pid)]:
                    raise ValueError("E_TEST_LISTENER_OWNER")
                observed = probe(port)
                break
            time.sleep(0.2)
        if observed is None:
            raise ValueError("E_TEST_RUNTIME_TIMEOUT")
        if observed["models"] or observed["runningModels"]:
            raise ValueError("E_TEST_NOT_EMPTY")
        model_report = exercise_models(root, port) if model_operations else None
    if any(found == port for _address, found, _pid in windows_records()):
        raise ValueError("E_TEST_RUNTIME_NOT_STOPPED")
    report = {
        "scope": "installer-ollama-development-fixture",
        "sourceSha256": expected,
        "authenticodePublisherVerified": True,
        "runtimeVersion": observed["version"],
        "actualWindowsTcpOwnerVerified": True,
        "actualEmptyRuntimeApiProbe": True,
        "runtimeProcessStopped": True,
        "existingRuntimeUsedOrChanged": False,
        "modelDownloadsOrGeneration": model_operations,
        "modelOperationEvidence": model_report,
        "scmOrColdBootAcceptance": False,
        "kyrionAiConnected": False,
        "models": [],
    }
    (root / "report.json").write_text(json.dumps(report, indent=2))
    return {"report": str(root / "report.json"), **report}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--exercise-model-download", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            exercise(
                args.executable,
                args.sha256,
                args.work,
                model_operations=args.exercise_model_download,
            )
        )
    )
