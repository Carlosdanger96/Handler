"""Container sandbox: runs worker/evaluator commands inside a Docker container."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .base import Sandbox, SandboxError


class ContainerSandbox(Sandbox):
    def __init__(
        self,
        repo_path: str | Path,
        image: str = "python:3.12-slim",
        work_root: str | Path | None = None,
    ) -> None:
        self.repo = Path(repo_path).resolve()
        if not self.repo.is_dir():
            raise SandboxError(f"target repo not found: {self.repo}")
        self.image = image
        root = Path(work_root) if work_root else Path(tempfile.mkdtemp(prefix="handler-ctr-"))
        root.mkdir(parents=True, exist_ok=True)
        self.path = (root / "workspace").resolve()
        self.scratch = (root / "scratch").resolve()
        self.scratch.mkdir(parents=True, exist_ok=True)
        self._prepared = False

    @staticmethod
    def available() -> bool:
        return shutil.which("docker") is not None

    def prepare(self) -> None:
        if not self.available():
            raise SandboxError("docker is not available on this host")
        shutil.copytree(self.repo, self.path, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git"))
        self._prepared = True

    def diff(self) -> str:
        raise SandboxError("container sandboxes capture diffs via 'handler export' from inside the container; use worktree for patch capture")

    def run(self, command: list[str], *, timeout: float, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        if not self._prepared:
            raise SandboxError("sandbox is not prepared")
        docker_cmd = [
            "docker", "run", "--rm",
            "-v", f"{self.path}:/workspace",
            "-v", f"{self.scratch}:/scratch",
            "-w", "/workspace",
        ]
        for key, value in (env or {}).items():
            docker_cmd += ["-e", f"{key}={value}"]
        docker_cmd += [self.image, *command]
        try:
            return subprocess.run(docker_cmd, capture_output=True, text=True, timeout=timeout + 30)
        except subprocess.TimeoutExpired as exc:
            raise SandboxError(f"container command timed out after {timeout}s") from exc

    def cleanup(self) -> None:
        if self.path.exists():
            shutil.rmtree(self.path, ignore_errors=True)
        if self.scratch.parent.exists() and not any(self.scratch.parent.iterdir()):
            shutil.rmtree(self.scratch.parent, ignore_errors=True)
        self._prepared = False


def create_sandbox(config: dict[str, Any], *, target_repo: str, base_ref: str = "HEAD", branch: str | None = None) -> Sandbox:
    from .worktree import GitWorktreeSandbox

    kind = str(config.get("type", "worktree")).lower()
    if kind == "worktree":
        return GitWorktreeSandbox(target_repo, base_ref=base_ref, branch=branch)
    if kind == "container":
        return ContainerSandbox(target_repo, image=str(config.get("image", "python:3.12-slim")))
    raise SandboxError(f"unknown sandbox type: {kind}")
