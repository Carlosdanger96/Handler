"""Evaluator interface: score a sandbox after a worker proposal was applied."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import Evaluation, Experiment
    from ..sandboxes.base import Sandbox


class EvaluatorError(RuntimeError):
    """The evaluator itself failed (distinct from a hypothesis failing its metrics)."""


class Evaluator(ABC):
    @abstractmethod
    def evaluate(self, *, sandbox: "Sandbox", experiment: "Experiment") -> "Evaluation": ...
