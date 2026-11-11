"""Actual Windows job-object tests; no services, tasks or user data touched."""

import ctypes
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from windows_process import ContainedProcess


@unittest.skipUnless(os.name == "nt", "Actual Windows process containment")
class ProcessTests(unittest.TestCase):
    def test_contained_tree_is_terminated_on_close(self):
        self.exercise(False)

    def test_supervisor_crash_cannot_leave_descendants_running(self):
        self.exercise(True)

    def exercise(self, crash):
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        environment = {
            key: os.environ[key]
            for key in ("SystemRoot", "WINDIR", "TEMP", "TMP")
            if key in os.environ
        }
        with tempfile.TemporaryDirectory(prefix="kyrion-job-test-") as directory:
            root = Path(directory)
            child = root / "child.py"
            child.write_text("""import json,os,subprocess,sys,time
from pathlib import Path
process=subprocess.Popen([sys.executable,'-I','-c','import time; time.sleep(120)'])
Path('pids.json').write_text(json.dumps([os.getpid(),process.pid]))
time.sleep(120)
""")
            process = None
            supervisor = None
            handles = []
            try:
                if crash:
                    launcher = root / "launcher.py"
                    launcher.write_text("""import sys,json,time,os
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from windows_process import ContainedProcess
root=Path.cwd()
process=ContainedProcess(Path(sys.executable),['-I',str(root/'child.py')],json.loads(sys.argv[2]),root)
while not (root/'release').exists(): time.sleep(0.02)
os._exit(7)
""")
                    supervisor = subprocess.Popen(
                        [
                            sys.executable,
                            "-I",
                            str(launcher),
                            str(Path(__file__).resolve().parents[1]),
                            json.dumps(environment),
                        ],
                        env=environment,
                        cwd=root,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                else:
                    process = ContainedProcess(
                        Path(sys.executable), ["-I", str(child)], environment, root
                    )
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline:
                    try:
                        pids = json.loads((root / "pids.json").read_text())
                        break
                    except (OSError, json.JSONDecodeError):
                        time.sleep(0.02)
                else:
                    self.fail("Actual child/grandchild did not start")
                for pid in pids:
                    handle = kernel.OpenProcess(0x100000, False, pid)
                    self.assertTrue(handle)
                    handles.append(handle)
                    self.assertEqual(kernel.WaitForSingleObject(handle, 0), 258)
                if crash:
                    (root / "release").write_text("stop own supervisor")
                    self.assertEqual(supervisor.wait(timeout=10), 7)
                else:
                    self.assertIsNone(process.poll())
                    process.close()
                    process.close()
                for handle in handles:
                    self.assertEqual(kernel.WaitForSingleObject(handle, 10000), 0)
            finally:
                if process:
                    process.close()
                if supervisor and supervisor.poll() is None:
                    supervisor.kill()
                    supervisor.wait(timeout=10)
                for handle in handles:
                    kernel.CloseHandle(handle)


if __name__ == "__main__":
    unittest.main()
