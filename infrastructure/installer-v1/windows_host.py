"""Native SCM host: all initialization runs after dispatcher connection."""

from __future__ import annotations

import ctypes
import os
import threading


def dispatch(name: str, workload) -> int:
    if os.name != "nt":
        raise ValueError("E_SERVICE_PLATFORM")
    from ctypes import wintypes as w

    main_type = ctypes.WINFUNCTYPE(None, w.DWORD, ctypes.POINTER(w.LPWSTR))
    handler_type = ctypes.WINFUNCTYPE(
        w.DWORD, w.DWORD, w.DWORD, ctypes.c_void_p, ctypes.c_void_p
    )

    class Status(ctypes.Structure):
        _fields_ = [
            (field, w.DWORD)
            for field in (
                "kind",
                "state",
                "accepted",
                "error",
                "specific",
                "checkpoint",
                "hint",
            )
        ]

    class Entry(ctypes.Structure):
        _fields_ = [("name", w.LPWSTR), ("main", main_type)]

    api = ctypes.WinDLL("advapi32", use_last_error=True)
    api.StartServiceCtrlDispatcherW.argtypes = [ctypes.POINTER(Entry)]
    api.StartServiceCtrlDispatcherW.restype = w.BOOL
    api.RegisterServiceCtrlHandlerExW.argtypes = [
        w.LPCWSTR,
        handler_type,
        ctypes.c_void_p,
    ]
    api.RegisterServiceCtrlHandlerExW.restype = w.HANDLE
    api.SetServiceStatus.argtypes = [w.HANDLE, ctypes.POINTER(Status)]
    api.SetServiceStatus.restype = w.BOOL
    stop = threading.Event()
    lock = threading.RLock()
    handle = None
    checkpoint = 0
    last = 1
    error = 0

    def report(state, failure=0):
        nonlocal checkpoint, last, error
        with lock:
            if stop.is_set() and state in {2, 4}:
                state = 3
            checkpoint = checkpoint + 1 if state in {2, 3} else 0
            last = state
            error = failure
            status = Status(
                16,
                state,
                5 if state == 4 else 0,
                1066 if failure else 0,
                failure,
                checkpoint,
                15000 if state in {2, 3} else 0,
            )
            if handle and not api.SetServiceStatus(handle, ctypes.byref(status)):
                stop.set()
                raise OSError("E_SERVICE_REPORT")

    @handler_type
    def handler(control, _event, _data, _context):
        try:
            if control in {1, 5}:
                with lock:
                    stop.set()
                    report(3)
                return 0
            if control == 4:
                report(last, error)
                return 0
            return 120
        except BaseException:  # noqa: BLE001 -- exceptions must not escape a Win32 callback
            stop.set()
            return 1

    @main_type
    def main(_count, _values):
        nonlocal handle
        handle = api.RegisterServiceCtrlHandlerExW(name, handler, None)
        if not handle:
            return
        failure = 0
        try:
            report(2)
            workload(stop, report)
        except BaseException:  # noqa: BLE001 -- exceptions must not escape a Win32 callback
            failure = 1
        finally:
            try:
                report(1, failure)
            except OSError:
                pass

    entries = (Entry * 2)(Entry(name, main), Entry(None, main_type()))
    if not api.StartServiceCtrlDispatcherW(entries):
        # Direct console invocation never falls back to launching a runtime.
        raise OSError("E_SERVICE_DISPATCH")
    return 0 if not error else 2
