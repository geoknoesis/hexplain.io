"""Windows processor jobs: assign a waiting launcher before it can spawn descendants."""

from __future__ import annotations

import ctypes
import json
import subprocess
import sys
from ctypes import wintypes
from pathlib import Path


class _Limits(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _IOCounters(ctypes.Structure):
    _fields_ = [
        (name, ctypes.c_ulonglong)
        for name in (
            "ReadOperationCount",
            "WriteOperationCount",
            "OtherOperationCount",
            "ReadTransferCount",
            "WriteTransferCount",
            "OtherTransferCount",
        )
    ]


class _ExtendedLimits(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _Limits),
        ("IoInfo", _IOCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


def _kernel32() -> ctypes.CDLL:
    if sys.platform != "win32":
        raise OSError("Windows process jobs require Windows")
    return ctypes.WinDLL("kernel32", use_last_error=True)


def _windows_error() -> OSError:
    if sys.platform != "win32":
        return OSError("Windows process jobs require Windows")
    return ctypes.WinError(ctypes.get_last_error())


class Job:
    """A noninheritable job handle whose closure kills all of its processes."""

    def __init__(self) -> None:
        self.api = _kernel32()
        for name, result, args in (
            ("CreateJobObjectW", wintypes.HANDLE, [ctypes.c_void_p, wintypes.LPCWSTR]),
            (
                "SetInformationJobObject",
                wintypes.BOOL,
                [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD],
            ),
            ("AssignProcessToJobObject", wintypes.BOOL, [wintypes.HANDLE, wintypes.HANDLE]),
            ("OpenProcess", wintypes.HANDLE, [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]),
            ("CloseHandle", wintypes.BOOL, [wintypes.HANDLE]),
        ):
            function = getattr(self.api, name)
            function.restype, function.argtypes = result, args
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise _windows_error()
        limits = _ExtendedLimits()
        limits.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            error = _windows_error()
            self.close()
            raise error

    def assign(self, pid: int) -> None:
        process = self.api.OpenProcess(0x0101, False, pid)  # SET_QUOTA | TERMINATE
        if not process:
            raise _windows_error()
        try:
            if not self.api.AssignProcessToJobObject(self.handle, process):
                raise _windows_error()
        finally:
            self.api.CloseHandle(process)

    def close(self) -> None:
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None


def launch(command: list[str], cwd: Path, job: Job) -> subprocess.Popen[str]:
    """The launcher waits for assignment; its descendants inherit the job even after it exits."""
    bootstrap = (
        "import json,subprocess,sys; "
        "token=sys.stdin.buffer.read(1); "
        "sys.exit(subprocess.call(json.loads(sys.argv[1]),stdin=subprocess.DEVNULL) if token==b'1' else 1)"
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", bootstrap, json.dumps(command)],
        cwd=cwd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert proc.stdin is not None
    try:
        job.assign(proc.pid)
        proc.stdin.write("1")
        proc.stdin.flush()
    except BaseException:
        proc.kill()
        proc.wait(timeout=10)
        raise
    finally:
        proc.stdin.close()
    return proc
