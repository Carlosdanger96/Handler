"""Pytest-based deterministic evaluator.

Runs the campaign's benchmark tests inside the sandbox. The score is
passed / total; ok means every benchmark test passed. If the benchmark writes
``handler_metrics.json`` in the sandbox root, its entries are merged into the
metric payload.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from ..models import Evaluation, Experiment
from ..sandboxes.base import Sandbox, SandboxError
from .base import Evaluator, EvaluatorError

_PASSED_RE = re.compile(r"(\d+)\s+passed")
_FAILED_RE = re.compile(r"(\d+)\s+failed")
_ERROR_RE = re.compile(r"(\d+)\s+errors?")


class PytestEvaluator(Evaluator):
    def __init__(
        self,
        test_paths: list[str] | None = None,
        timeout: float = 300.0,
        python: str = "python3",
        extra_args: list[str] | None = None,
    ) -> None:
        self.test_paths = list(test_paths) if test_paths else ["tests"]
        self.timeout = float(timeout)
        self.python = python
        self.extra_args = list(extra_args or [])

    def evaluate(self, *, sandbox: Sandbox, experiment: Experiment) -> Evaluation:
        command = [
            self.python, "-m", "pytest",
            *self.test_paths,
            "-q", "--tb=short", "-p", "no:cacheprovider",
            *self.extra_args,
        ]
        started = time.monotonic()
        try:
            result = sandbox.run(command, timeout=self.timeout)
        except SandboxError as exc:
            raise EvaluatorError(str(exc)) from exc
        duration = time.monotonic() - started
        log = f"$ {' '.join(command)}\n{result.stdout}\n{result.stderr}".strip()
        output = result.stdout + "\n" + result.stderr

        passed = int(_PASSED_RE.search(output).group(1)) if _PASSED_RE.search(output) else 0
        failed = int(_FAILED_RE.search(output).group(1)) if _FAILED_RE.search(output) else 0
        errors = int(_ERROR_RE.search(output).group(1)) if _ERROR_RE.search(output) else 0
        total = passed + failed + errors
        score = (passed / total) if total else 0.0
        ok = result.returncode == 0 and passed > 0 and failed == 0 and errors == 0

        metrics: dict[str, Any] = {
            "returncode": result.returncode,
            "tests_passed": passed,
            "tests_failed": failed,
            "tests_error": errors,
        }
        metrics_file = Path(sandbox.path) / "handler_metrics.json"
        if metrics_file.is_file():
            try:
                metrics.update(json.loads(metrics_file.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                metrics["metrics_file_error"] = "handler_metrics.json was not valid JSON"

        return Evaluation(
            experiment_id=experiment.experiment_id,
            ok=ok,
            score=round(score, 6),
            metrics=metrics,
            passed=passed,
            failed=failed,
            duration_seconds=round(duration, 3),
            log=log,
        )


def create_evaluator(config: dict[str, Any]) -> Evaluator:
    config = dict(config or {})
    kind = str(config.get("type", "pytest")).lower()
    if kind != "pytest":
        raise EvaluatorError(f"unknown evaluator type: {kind}")
    return PytestEvaluator(
        test_paths=config.get("test_paths"),
        timeout=float(config.get("timeout", 300.0)),
        python=str(config.get("python", "python3")),
        extra_args=config.get("extra_args"),
    )
