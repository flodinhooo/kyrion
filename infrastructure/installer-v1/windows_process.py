"""Native child-tree containment. No command entrypoint or machine registration.

Start suspended, assign to a noninheritable kill-on-close job, then resume.
Failure to establish containment never leaves a running uncontained child.
"""

from __future__ import annotations

import ctypes
import os
import subprocess
from pathlib import Path


class ContainedProcess:
    def __init__(
        self,
        executable: Path,
        arguments: list[str],
        environment: dict[str, str],
        directory: Path,
    ):
        if os.name != "nt":
            raise ValueError("E_WINDOWS_PROCESS_PLATFORM")
        if (
            not executable.is_absolute()
            or not executable.is_file()
            or not directory.is_absolute()
            or not directory.is_dir()
            or any(
                "\x00" in value
                for value in [str(executable), str(directory), *arguments]
            )
            or not environment
            or len({key.casefold() for key in environment}) != len(environment)
            or any(
                not key or "=" in key or "\x00" in key or "\x00" in value
                for key, value in environment.items()
            )
        ):
            raise ValueError("E_WINDOWS_PROCESS_INPUT")
        from ctypes import wintypes as w

        class Startup(ctypes.Structure):
            _fields_ = [
                ("cb", w.DWORD),
                ("reserved", w.LPWSTR),
                ("desktop", w.LPWSTR),
                ("title", w.LPWSTR),
                ("x", w.DWORD),
                ("y", w.DWORD),
                ("xsize", w.DWORD),
                ("ysize", w.DWORD),
                ("charsx", w.DWORD),
                ("charsy", w.DWORD),
                ("fill", w.DWORD),
                ("flags", w.DWORD),
                ("show", w.WORD),
                ("reserved_count", w.WORD),
                ("reserved_bytes", ctypes.POINTER(ctypes.c_byte)),
                ("stdin", w.HANDLE),
                ("stdout", w.HANDLE),
                ("stderr", w.HANDLE),
            ]

        class Process(ctypes.Structure):
            _fields_ = [
                ("process", w.HANDLE),
                ("thread", w.HANDLE),
                ("pid", w.DWORD),
                ("tid", w.DWORD),
            ]

        class BasicLimit(ctypes.Structure):
            _fields_ = [
                ("process_time", ctypes.c_int64),
                ("job_time", ctypes.c_int64),
                ("flags", w.DWORD),
                ("minimum_working_set", ctypes.c_size_t),
                ("maximum_working_set", ctypes.c_size_t),
                ("active_processes", w.DWORD),
                ("affinity", ctypes.c_size_t),
                ("priority", w.DWORD),
                ("scheduling", w.DWORD),
            ]

        class IoCounters(ctypes.Structure):
            _fields_ = [
                (name, ctypes.c_uint64)
                for name in (
                    "read_ops",
                    "write_ops",
                    "other_ops",
                    "read_bytes",
                    "write_bytes",
                    "other_bytes",
                )
            ]

        class ExtendedLimit(ctypes.Structure):
            _fields_ = [
                ("basic", BasicLimit),
                ("io", IoCounters),
                ("process_memory", ctypes.c_size_t),
                ("job_memory", ctypes.c_size_t),
                ("peak_process_memory", ctypes.c_size_t),
                ("peak_job_memory", ctypes.c_size_t),
            ]

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        declarations = {
            "CreateJobObjectW": ([ctypes.c_void_p, w.LPCWSTR], w.HANDLE),
            "SetInformationJobObject": (
                [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD],
                w.BOOL,
            ),
            "CreateProcessW": (
                [
                    w.LPCWSTR,
                    w.LPWSTR,
                    ctypes.c_void_p,
                    ctypes.c_void_p,
                    w.BOOL,
                    w.DWORD,
                    ctypes.c_void_p,
                    w.LPCWSTR,
                    ctypes.POINTER(Startup),
                    ctypes.POINTER(Process),
                ],
                w.BOOL,
            ),
            "AssignProcessToJobObject": ([w.HANDLE, w.HANDLE], w.BOOL),
            "ResumeThread": ([w.HANDLE], w.DWORD),
            "TerminateProcess": ([w.HANDLE, w.UINT], w.BOOL),
            "WaitForSingleObject": ([w.HANDLE, w.DWORD], w.DWORD),
            "GetExitCodeProcess": ([w.HANDLE, ctypes.POINTER(w.DWORD)], w.BOOL),
            "CloseHandle": ([w.HANDLE], w.BOOL),
        }
        for name, (parameters, result) in declarations.items():
            function = getattr(kernel, name)
            function.argtypes = parameters
            function.restype = result
        self.kernel = kernel
        self.process = None
        self.job = kernel.CreateJobObjectW(None, None)
        if not self.job:
            raise OSError("E_WINDOWS_JOB_CREATE")
        information = Process()
        try:
            limits = ExtendedLimit()
            limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not kernel.SetInformationJobObject(
                self.job, 9, ctypes.byref(limits), ctypes.sizeof(limits)
            ):
                raise OSError("E_WINDOWS_JOB_LIMIT")
            startup = Startup()
            startup.cb = ctypes.sizeof(startup)
            command = ctypes.create_unicode_buffer(
                subprocess.list2cmdline([str(executable), *arguments])
            )
            block = ctypes.create_unicode_buffer(
                "\x00".join(
                    key + "=" + value
                    for key, value in sorted(
                        environment.items(), key=lambda pair: pair[0].upper()
                    )
                )
                + "\x00\x00"
            )
            # Null security attributes and FALSE inheritance prevent child access
            # to the job handle; descendants cannot keep the kill-on-close job alive.
            if not kernel.CreateProcessW(
                str(executable),
                command,
                None,
                None,
                False,
                0x08000000 | 0x00000004 | 0x00000400,
                block,
                str(directory),
                ctypes.byref(startup),
                ctypes.byref(information),
            ):
                raise OSError("E_WINDOWS_PROCESS_CREATE")
            self.process = information.process
            self.pid = information.pid
            if not kernel.AssignProcessToJobObject(self.job, self.process):
                raise OSError("E_WINDOWS_JOB_ASSIGN")
            if kernel.ResumeThread(information.thread) == 0xFFFFFFFF:
                raise OSError("E_WINDOWS_PROCESS_RESUME")
        except BaseException:
            if self.process:
                kernel.TerminateProcess(self.process, 1)
                kernel.WaitForSingleObject(self.process, 5000)
            self.close()
            raise
        finally:
            if information.thread:
                kernel.CloseHandle(information.thread)

    def poll(self) -> int | None:
        from ctypes import wintypes

        if not self.process:
            raise ValueError("E_WINDOWS_PROCESS_CLOSED")
        result = self.kernel.WaitForSingleObject(self.process, 0)
        if result == 258:
            return None
        if result != 0:
            raise OSError("E_WINDOWS_PROCESS_WAIT")
        code = wintypes.DWORD()
        if not self.kernel.GetExitCodeProcess(self.process, ctypes.byref(code)):
            raise OSError("E_WINDOWS_PROCESS_STATUS")
        return code.value

    def close(self) -> None:
        if self.job:
            if not self.kernel.CloseHandle(self.job):
                raise OSError("E_WINDOWS_JOB_CLOSE")
            self.job = None
        if self.process:
            try:
                if self.kernel.WaitForSingleObject(self.process, 10000) != 0:
                    raise OSError("E_WINDOWS_PROCESS_STOP")
            finally:
                self.kernel.CloseHandle(self.process)
                self.process = None

    def __enter__(self):
        return self

    def __exit__(self, _kind, _value, _traceback):
        self.close()
