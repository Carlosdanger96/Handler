"""Worker adapter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..models import Campaign, Hypothesis, Proposal
    from ..sandboxes.base import Sandbox


class WorkerError(RuntimeError):
    """A worker ran but failed to produce a usable proposal."""


class WorkerUnavailable(WorkerError):
    """The worker's runtime (CLI, model, network) is not available."""


class WorkerAdapter(ABC):
    name: str

    @abstractmethod
    def propose(
        self,
        *,
        sandbox: "Sandbox",
        hypothesis: "Hypothesis",
        campaign: "Campaign",
        context: dict[str, Any],
    ) -> tuple["Proposal", str]:
        """Run inside the sandbox and return (proposal, worker log)."""
