"""Bounded local process execution with truthful isolation capabilities."""
from __future__ import annotations

import os
import signal
import subprocess
import time
import ctypes
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping, Sequence


SAFE_ENV_KEYS = {
    "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "TEMP", "TMP", "PATH",
    "USERPROFILE", "APPDATA", "LOCALAPPDATA", "PROGRAMDATA", "NUMBER_OF_PROCESSORS",
    "PROCESSOR_ARCHITECTURE", "R_HOME", "R_LIBS", "R_LIBS_USER", "LANG", "LC_ALL",
}
SECRET_MARKERS = ("TOKEN", "SECRET", "PASSWORD", "API_KEY", "CREDENTIAL")


class _WindowsJob:
    """Kill-on-close Job Object for one subprocess tree."""
    def __init__(self) -> None:
        self.handle = None
        if os.name != "nt":
            return
        from ctypes import wintypes
        class Basic(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
                        ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                        ("SchedulingClass", wintypes.DWORD)]
        class IoCounters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in
                        ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                         "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]
        class Extended(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", Basic), ("IoInfo", IoCounters),
                        ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        kernel32.SetInformationJobObject.restype = wintypes.BOOL
        kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
        kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel32.TerminateJobObject.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        handle = kernel32.CreateJobObjectW(None, None)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        info = Extended(); info.BasicLimitInformation.LimitFlags = 0x00002000
        if not kernel32.SetInformationJobObject(handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
            kernel32.CloseHandle(handle); raise ctypes.WinError(ctypes.get_last_error())
        self.handle = handle; self.kernel32 = kernel32

    def assign(self, process: subprocess.Popen[str]) -> None:
        if self.handle and not self.kernel32.AssignProcessToJobObject(self.handle, int(process._handle)):
            raise ctypes.WinError(ctypes.get_last_error())

    def terminate(self) -> bool:
        return bool(self.handle and self.kernel32.TerminateJobObject(self.handle, 1))

    def close(self) -> None:
        if self.handle:
            self.kernel32.CloseHandle(self.handle); self.handle = None


@dataclass(frozen=True)
class ExecutionPolicy:
    workspace_mode: str = "project-write"
    network_policy: str = "deny"
    allowed_roots: tuple[str, ...] = ()
    environment_allowlist: tuple[str, ...] = tuple(sorted(SAFE_ENV_KEYS))
    require_os_network_isolation: bool = False

    def __post_init__(self) -> None:
        if self.workspace_mode not in {"read-only", "project-write", "restricted-data"}:
            raise ValueError("Unsupported workspace mode")
        if self.network_policy not in {"deny", "allow"}:
            raise ValueError("Unsupported network policy")


@dataclass(frozen=True)
class ProcessResult:
    returncode: int
    stdout: str
    stderr: str
    elapsed_seconds: float
    timed_out: bool
    termination: str
    isolation: dict


class LocalProcessBoundary:
    """No-shell runner with process-tree termination and explicit capability gaps.

    Windows path and process lifetime controls are enforced.  OS-level filesystem
    and network isolation are not available on this host, so callers may demand
    fail-closed behavior through ``require_os_network_isolation``.
    """

    def __init__(self, project_root: str | Path):
        self.project_root = Path(project_root).resolve()

    def _allowed_roots(self, policy: ExecutionPolicy) -> list[Path]:
        roots = [self.project_root]
        roots.extend(Path(value).resolve() for value in policy.allowed_roots)
        return roots

    def _inside(self, path: Path, roots: list[Path]) -> bool:
        return any(path == root or path.is_relative_to(root) for root in roots)

    def _environment(self, policy: ExecutionPolicy, overrides: Mapping[str, str] | None) -> dict[str, str]:
        allowed = set(policy.environment_allowlist)
        environment = {key: value for key, value in os.environ.items()
                       if key.upper() in allowed and not any(marker in key.upper() for marker in SECRET_MARKERS)}
        for key, value in (overrides or {}).items():
            if key.upper() not in allowed or any(marker in key.upper() for marker in SECRET_MARKERS):
                raise PermissionError(f"Environment variable is not allowed: {key}")
            environment[key] = str(value)
        environment["RESEARCH_OS_NETWORK_POLICY"] = policy.network_policy
        return environment

    @staticmethod
    def _terminate_tree(process: subprocess.Popen[str], job: _WindowsJob | None = None) -> str:
        if process.poll() is not None:
            return "already-exited"
        if os.name == "nt":
            if job and job.terminate():
                return "windows-job-object"
            completed = subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                       capture_output=True, text=True, timeout=15, check=False)
            if completed.returncode == 0:
                return "taskkill-process-tree"
            process.kill(); return "parent-kill-fallback"
        os.killpg(process.pid, signal.SIGKILL)
        return "kill-process-group"

    def run(self, command: Sequence[str | Path], *, cwd: str | Path, timeout: int | float,
            policy: ExecutionPolicy, environment: Mapping[str, str] | None = None) -> ProcessResult:
        if not command:
            raise ValueError("Command cannot be empty")
        if policy.network_policy == "deny" and policy.require_os_network_isolation:
            raise RuntimeError("OS-level network isolation is unavailable on this local Windows backend")
        roots = self._allowed_roots(policy); working = Path(cwd).resolve()
        if not self._inside(working, roots):
            raise PermissionError("Working directory escapes allowed roots")
        executable = Path(command[0]).resolve()
        if not executable.is_file():
            raise FileNotFoundError(executable)
        for value in command[1:]:
            text = str(value)
            candidate = Path(text)
            if candidate.is_absolute() and not self._inside(candidate.resolve(), roots):
                raise PermissionError(f"Command path argument escapes allowed roots: {text}")
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        started = time.monotonic()
        job = _WindowsJob() if os.name == "nt" else None
        process = subprocess.Popen([str(value) for value in command], cwd=working, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
                                   env=self._environment(policy, environment), creationflags=flags,
                                   start_new_session=os.name != "nt")
        if job:
            try:
                job.assign(process)
            except Exception:
                process.kill(); process.communicate(); job.close(); raise
        timed_out = False; termination = "normal"
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True; termination = self._terminate_tree(process, job)
            stdout, stderr = process.communicate(timeout=15)
        finally:
            if job: job.close()
        isolation = {"backend": "local-process", "workspace_mode": policy.workspace_mode,
                     "path_boundary": "enforced-for-cwd-and-absolute-path-arguments",
                     "environment_allowlist": "enforced", "process_tree_control": "windows-job-object" if os.name == "nt" else "process-group",
                     "network_policy": policy.network_policy, "network_enforcement": "declaration-only",
                     "filesystem_enforcement": "path-policy-not-os-sandbox"}
        if job:
            job.close()
        return ProcessResult(process.returncode, stdout, stderr, round(time.monotonic() - started, 3),
                             timed_out, termination, isolation)
