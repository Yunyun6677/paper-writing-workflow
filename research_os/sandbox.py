"""Framework-neutral execution backends for generated research code.

The local backend is deliberately honest about its limits: it enforces a
project-root path policy, an environment allow-list, a wall-clock timeout and
process-tree termination, but it is not an operating-system security boundary.
The Docker backend is the stronger target and fails closed when Docker is not
available.  Neither backend accepts a shell command string.
"""
from __future__ import annotations

import shutil
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping, Sequence

from .isolation import ExecutionPolicy, LocalProcessBoundary, ProcessResult


@dataclass(frozen=True)
class SandboxRequest:
    command: tuple[str, ...]
    working_directory: str = "."
    timeout_seconds: int = 300
    workspace_mode: str = "project-write"
    network_policy: str = "deny"
    environment: Mapping[str, str] | None = None
    cpu_limit: float | None = None
    memory_limit_mb: int | None = None

    def __post_init__(self) -> None:
        if not self.command:
            raise ValueError("sandbox command cannot be empty")
        if self.timeout_seconds < 1:
            raise ValueError("timeout_seconds must be positive")
        if self.cpu_limit is not None and self.cpu_limit <= 0:
            raise ValueError("cpu_limit must be positive")
        if self.memory_limit_mb is not None and self.memory_limit_mb < 32:
            raise ValueError("memory_limit_mb must be at least 32")


@dataclass(frozen=True)
class SandboxResult:
    returncode: int
    stdout: str
    stderr: str
    elapsed_seconds: float
    timed_out: bool
    termination: str
    isolation: dict

    @classmethod
    def from_process(cls, result: ProcessResult) -> "SandboxResult":
        return cls(**asdict(result))


class SandboxBackend(ABC):
    backend_id: str

    @abstractmethod
    def available(self) -> bool:
        """Return whether this backend can execute on the current host."""

    @abstractmethod
    def run(self, request: SandboxRequest) -> SandboxResult:
        """Execute one bounded argv request and return a structured observation."""


class LocalRestrictedBackend(SandboxBackend):
    """Process-isolated fallback for hosts without a container runtime."""

    backend_id = "local-restricted"

    def __init__(self, project_root: str | Path):
        self.project_root = Path(project_root).resolve()
        self.boundary = LocalProcessBoundary(self.project_root)

    def available(self) -> bool:
        return self.project_root.is_dir()

    def run(self, request: SandboxRequest) -> SandboxResult:
        working = (self.project_root / request.working_directory).resolve()
        policy = ExecutionPolicy(
            workspace_mode=request.workspace_mode,
            network_policy=request.network_policy,
            allowed_roots=(str(Path(request.command[0]).resolve().parent),),
            require_os_network_isolation=False,
        )
        result = self.boundary.run(
            request.command,
            cwd=working,
            timeout=request.timeout_seconds,
            policy=policy,
            environment=request.environment,
        )
        isolation = dict(result.isolation)
        isolation.update({
            "sandbox_backend": self.backend_id,
            "cpu_limit": "not-enforced",
            "memory_limit": "not-enforced",
            "production_security_boundary": False,
        })
        return SandboxResult(
            result.returncode, result.stdout, result.stderr,
            result.elapsed_seconds, result.timed_out, result.termination, isolation,
        )


class DockerSandboxBackend(SandboxBackend):
    """Docker execution boundary with read-only inputs and bounded resources.

    The image must already exist locally.  Pulling images and enabling network
    access are deliberately outside this adapter.
    """

    backend_id = "docker"

    def __init__(self, project_root: str | Path, image: str,
                 docker_executable: str | Path | None = None):
        self.project_root = Path(project_root).resolve()
        self.image = image
        discovered = str(docker_executable) if docker_executable else shutil.which("docker")
        self.docker_executable = Path(discovered).resolve() if discovered else None

    def available(self) -> bool:
        return bool(self.docker_executable and self.docker_executable.is_file())

    def run(self, request: SandboxRequest) -> SandboxResult:
        if not self.available():
            raise FileNotFoundError("Docker is unavailable; DockerSandboxBackend remains staged")
        working = (self.project_root / request.working_directory).resolve()
        if not working.is_relative_to(self.project_root):
            raise PermissionError("Docker working directory escapes the project root")
        relative = working.relative_to(self.project_root).as_posix() or "."
        command: list[str] = [
            str(self.docker_executable), "run", "--rm", "--init",
            "--network", "none" if request.network_policy == "deny" else "bridge",
            "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--pids-limit", "128", "--mount",
            f"type=bind,src={self.project_root},dst=/workspace",
            "--workdir", f"/workspace/{relative}",
        ]
        if request.cpu_limit is not None:
            command += ["--cpus", str(request.cpu_limit)]
        if request.memory_limit_mb is not None:
            command += ["--memory", f"{request.memory_limit_mb}m"]
        for key, value in sorted((request.environment or {}).items()):
            command += ["--env", f"{key}={value}"]
        command += [self.image, *request.command]
        boundary = LocalProcessBoundary(self.project_root)
        result = boundary.run(
            command, cwd=self.project_root, timeout=request.timeout_seconds,
            policy=ExecutionPolicy("project-write", "allow", (str(self.docker_executable.parent),)),
        )
        isolation = dict(result.isolation)
        isolation.update({
            "sandbox_backend": self.backend_id,
            "container_image": self.image,
            "container_network": request.network_policy,
            "cpu_limit": request.cpu_limit,
            "memory_limit_mb": request.memory_limit_mb,
            "production_security_boundary": True,
        })
        return SandboxResult(
            result.returncode, result.stdout, result.stderr,
            result.elapsed_seconds, result.timed_out, result.termination, isolation,
        )
