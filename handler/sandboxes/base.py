"""Sandbox interface: an isolated copy of the target repo where workers run."""

from __future__ import annotations

import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class SandboxError(RuntimeError):
    """Raised when a sandbox cannot be prepared, executed in, or cleaned up."""


class Sandbox(ABC):
    path: Path
    scratch: Path

    @abstractmethod
    def prepare(self) -> None: ...

    @abstractmethod
    def diff(self) -> str: ...

    @abstractmethod
    def run(self, command: list[str], *, timeout: float, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]: ...

    @abstractmethod
    def cleanup(self) -> None: ...

    def __enter__(self) -> "Sandbox":
        self.prepare()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.cleanup()
