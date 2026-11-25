"""Protected-path enforcement and campaign budget/plateau/timeout controls."""

from __future__ import annotations

import fnmatch
import re
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import Budget, Experiment

DEFAULT_PROTECTED_PATHS: list[str] = [
    ".github/**",
    ".github/*",
    ".env",
    ".env*",
    "*.pem",
    "*.key",
    "secrets/**",
    "credentials/**",
    "deploy/**",
    "infra/**",
    "terraform/**",
]

_DIFF_FILE_RE = re.compile(r"^diff --git a/(?P<a>\S+) b/(?P<b>\S+)$", re.MULTILINE)
_NEW_FILE_RE = re.compile(r"^\+\+\+ b/(?P<b>\S+)$", re.MULTILINE)


def patch_files(patch: str) -> list[str]:
    """Extract the list of file paths touched by a unified diff."""
    files: list[str] = []
    for match in _DIFF_FILE_RE.finditer(patch):
        files.append(match.group("b"))
    for match in _NEW_FILE_RE.finditer(patch):
        candidate = match.group("b")
        if candidate not in files:
            files.append(candidate)
    return files


def _matches(path: str, pattern: str) -> bool:
    if fnmatch.fnmatch(path, pattern):
        return True
    if fnmatch.fnmatch(path, f"**/{pattern}"):
        return True
    return any(fnmatch.fnmatch(part, pattern) for part in path.split("/"))


class ProtectedPathsPolicy:
    """Rejects proposals whose diff touches protected paths."""

    def __init__(self, patterns: list[str] | None = None) -> None:
        self.patterns = list(patterns) if patterns else list(DEFAULT_PROTECTED_PATHS)

    def violations(self, patch: str) -> list[str]:
        offenders: list[str] = []
        for path in patch_files(patch):
            if any(_matches(path, pattern) for pattern in self.patterns):
                offenders.append(path)
        return sorted(set(offenders))


class BudgetTracker:
    """Tracks experiment count, wall time, best score, and plateau state."""

    def __init__(self, budget: "Budget", clock=time.monotonic) -> None:
        self.budget = budget
        self._clock = clock
        self.experiments_run = 0
        self.started_at = clock()
        self.best_score: float | None = None
        self.plateau_count = 0

    def elapsed(self) -> float:
        return self._clock() - self.started_at

    def record(self, experiment: "Experiment") -> None:
        self.experiments_run += 1
        evaluation = experiment.evaluation
        if evaluation is not None:
            if self.best_score is None or evaluation.score > self.best_score:
                self.best_score = evaluation.score
                self.plateau_count = 0
            else:
                self.plateau_count += 1

    def should_stop(self) -> tuple[bool, str]:
        if self.experiments_run >= self.budget.max_experiments:
            return True, f"experiment budget exhausted ({self.experiments_run}/{self.budget.max_experiments})"
        if self.elapsed() >= self.budget.max_wall_seconds:
            return True, f"campaign wall-time budget exhausted ({self.elapsed():.1f}s)"
        if self.budget.plateau_limit > 0 and self.plateau_count >= self.budget.plateau_limit:
            return True, f"plateau detected: {self.plateau_count} consecutive experiments without improvement"
        return False, ""
