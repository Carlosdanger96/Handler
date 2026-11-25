"""Safety policies: protected paths, resource limits, and approval gating."""

from .approval import ApprovalGate, ApprovalRequired
from .safety import DEFAULT_PROTECTED_PATHS, BudgetTracker, ProtectedPathsPolicy, patch_files

__all__ = [
    "ApprovalGate",
    "ApprovalRequired",
    "BudgetTracker",
    "DEFAULT_PROTECTED_PATHS",
    "ProtectedPathsPolicy",
    "patch_files",
]
