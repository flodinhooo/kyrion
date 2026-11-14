"""Run only a copied verified Ollama CLI in an empty owned developer fixture.

No installed instance, user model, generation, pull, service or cloud is used.
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

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from host import reject_links
from local_listeners import windows_records
from ollama_runtime import probe
from windows_process import ContainedProcess
from windows_system import base_environment, system_directory


def exercise(executable: Path, expected: str, parent: Path) -> dict:
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
        "modelDownloadsOrGeneration": False,
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
    args = parser.parse_args()
    print(json.dumps(exercise(args.executable, args.sha256, args.work)))
