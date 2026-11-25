"""Isolated execution sandboxes. Workers never touch the primary checkout."""

from .base import Sandbox, SandboxError
from .container import ContainerSandbox
from .worktree import GitWorktreeSandbox

__all__ = ["ContainerSandbox", "GitWorktreeSandbox", "Sandbox", "SandboxError"]
