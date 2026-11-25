"""Approval gate: nothing merges or becomes validated memory without explicit approval."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from ..models import Experiment


class ApprovalRequired(RuntimeError):
    """Raised when an action requires explicit human approval."""


class _LedgerLike(Protocol):
    def approve_experiment(self, experiment_id: str, approver: str) -> "Experiment": ...


class ApprovalGate:
    def __init__(self, ledger: _LedgerLike, auto_approve: bool = False) -> None:
        self.ledger = ledger
        self.auto_approve = auto_approve

    def approve(self, experiment_id: str, approver: str) -> "Experiment":
        if not approver or not approver.strip():
            raise ValueError("approver identity is required")
        return self.ledger.approve_experiment(experiment_id, approver.strip())

    def ensure_approved(self, experiment: "Experiment") -> None:
        if self.auto_approve:
            return
        if experiment.status != "approved" or not experiment.approved_by:
            raise ApprovalRequired(
                f"experiment {experiment.experiment_id} requires explicit approval before "
                "merging or promoting knowledge"
            )
