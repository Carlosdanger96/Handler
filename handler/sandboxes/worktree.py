"""Git worktree sandbox: a detached worktree of the target repo in a temp directory."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .base import Sandbox, SandboxError


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
    )


class GitWorktreeSandbox(Sandbox):
    def __init__(self, repo_path: str | Path, base_ref: str = "HEAD", work_root: str | Path | None = None, branch: str | None = None) -> None:
        self.repo = Path(repo_path).resolve()
        if not self.repo.is_dir():
            raise SandboxError(f"target repo not found: {self.repo}")
        check = _git(self.repo, "rev-parse", "--is-inside-work-tree")
        if check.returncode != 0 or check.stdout.strip() != "true":
            raise SandboxError(f"target is not a git repository: {self.repo}")
        self.base_ref = base_ref
        self.branch = branch
        root = Path(work_root) if work_root else Path(tempfile.mkdtemp(prefix="handler-wt-"))
        root.mkdir(parents=True, exist_ok=True)
        self.path = (root / "sandbox").resolve()
        self.scratch = (root / "scratch").resolve()
        self.scratch.mkdir(parents=True, exist_ok=True)
        if self.path == self.repo or self.repo in self.path.parents:
            raise SandboxError("sandbox path must live outside the primary checkout")
        if self.path.exists():
            raise SandboxError(f"sandbox path already exists: {self.path}")
        self._prepared = False

    def prepare(self) -> None:
        args = ["worktree", "add"]
        if self.branch:
            args += ["-b", self.branch]
        else:
            args += ["--detach"]
        args += [str(self.path), self.base_ref]
        result = _git(self.repo, *args)
        if result.returncode != 0:
            raise SandboxError(f"git worktree add failed: {result.stderr.strip()}")
        self._prepared = True

    def diff(self) -> str:
        _git(self.path, "add", "-A")
        result = _git(self.path, "diff", "--cached")
        if result.returncode != 0:
            raise SandboxError(f"git diff failed: {result.stderr.strip()}")
        return result.stdout

    def run(self, command: list[str], *, timeout: float, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        if not self._prepared:
            raise SandboxError("sandbox is not prepared")
        merged = dict(os.environ)
        if env:
            merged.update(env)
        try:
            return subprocess.run(
                command,
                cwd=self.path,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=merged,
            )
        except subprocess.TimeoutExpired as exc:
            raise SandboxError(f"command timed out after {timeout}s: {command[0]}") from exc

    def cleanup(self) -> None:
        if self._prepared:
            _git(self.repo, "worktree", "remove", "--force", str(self.path))
            _git(self.repo, "worktree", "prune")
            if self.branch:
                _git(self.repo, "branch", "-D", self.branch)
            self._prepared = False
        if self.path.exists():
            shutil.rmtree(self.path, ignore_errors=True)
        if self.scratch.parent.exists() and not any(self.scratch.parent.iterdir()):
            shutil.rmtree(self.scratch.parent, ignore_errors=True)
