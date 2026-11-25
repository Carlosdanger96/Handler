"""CLI- and script-backed worker adapters.

Workers only ever execute inside a sandbox (worktree/container); the resulting
change is captured as a unified diff so the primary checkout is never edited.
"""

from __future__ import annotations

import shutil
from typing import Any

from ..models import Campaign, Hypothesis, Proposal
from ..sandboxes.base import Sandbox, SandboxError
from .base import WorkerAdapter, WorkerError, WorkerUnavailable

PROMPT_TEMPLATE = """Objective: {objective}

Project context from memory:
{context}

Hypothesis to test: {hypothesis}

Propose the smallest change in this repository that tests the hypothesis.
Edit files directly; the harness captures your change as a diff.
"""


def render_prompt(*, campaign: Campaign, hypothesis: Hypothesis, context: dict[str, Any]) -> str:
    context_text = context.get("context_text") or "(no prior experience recorded)"
    return PROMPT_TEMPLATE.format(
        objective=campaign.objective,
        context=context_text,
        hypothesis=hypothesis.statement,
    )


def _format_command(template: list[str], *, prompt: str, sandbox: Sandbox) -> list[str]:
    values = {
        "prompt": prompt,
        "sandbox_path": str(sandbox.path),
        "scratch_path": str(sandbox.scratch),
    }
    return [part.format(**values) for part in template]


class CliWorker(WorkerAdapter):
    """Runs an external CLI command inside the sandbox and captures the diff."""

    def __init__(self, name: str, command: list[str], timeout: float = 600.0, binary: str | None = None) -> None:
        self.name = name
        self.command = list(command)
        self.timeout = float(timeout)
        self.binary = binary or command[0]

    def ensure_available(self) -> None:
        if shutil.which(self.binary) is None:
            raise WorkerUnavailable(f"worker '{self.name}' requires '{self.binary}' on PATH")

    def propose(
        self,
        *,
        sandbox: Sandbox,
        hypothesis: Hypothesis,
        campaign: Campaign,
        context: dict[str, Any],
    ) -> tuple[Proposal, str]:
        self.ensure_available()
        prompt = render_prompt(campaign=campaign, hypothesis=hypothesis, context=context)
        command = _format_command(self.command, prompt=prompt, sandbox=sandbox)
        try:
            result = sandbox.run(command, timeout=self.timeout)
        except SandboxError as exc:
            raise WorkerError(str(exc)) from exc
        log = f"$ {' '.join(command)}\n{result.stdout}\n{result.stderr}".strip()
        if result.returncode != 0:
            raise WorkerError(f"worker command exited {result.returncode}: {result.stderr.strip()[:500]}")
        patch = sandbox.diff()
        if not patch.strip():
            raise WorkerError("worker produced no changes")
        return (
            Proposal(
                hypothesis_id=hypothesis.hypothesis_id,
                worker=self.name,
                patch=patch,
                summary=hypothesis.statement,
            ),
            log,
        )


class ScriptWorker(CliWorker):
    """Runs a Python script (from the campaign definition) inside the sandbox."""

    def __init__(self, name: str, script: str, timeout: float = 600.0, python: str = "python3") -> None:
        self.script = script
        self.python = python
        super().__init__(name, [python, "{script_path}"], timeout=timeout, binary=python)

    def propose(
        self,
        *,
        sandbox: Sandbox,
        hypothesis: Hypothesis,
        campaign: Campaign,
        context: dict[str, Any],
    ) -> tuple[Proposal, str]:
        script_path = sandbox.scratch / "worker_script.py"
        script_path.write_text(self.script, encoding="utf-8")
        prompt = render_prompt(campaign=campaign, hypothesis=hypothesis, context=context)
        (sandbox.scratch / "prompt.txt").write_text(prompt, encoding="utf-8")
        command = [self.python, str(script_path)]
        try:
            result = sandbox.run(command, timeout=self.timeout)
        except SandboxError as exc:
            raise WorkerError(str(exc)) from exc
        log = f"$ {self.python} worker_script.py (hypothesis: {hypothesis.statement})\n{result.stdout}\n{result.stderr}".strip()
        if result.returncode != 0:
            raise WorkerError(f"worker script exited {result.returncode}: {result.stderr.strip()[:500]}")
        patch = sandbox.diff()
        if not patch.strip():
            raise WorkerError("worker produced no changes")
        return (
            Proposal(
                hypothesis_id=hypothesis.hypothesis_id,
                worker=self.name,
                patch=patch,
                summary=hypothesis.statement,
            ),
            log,
        )


class LocalScriptWorker(ScriptWorker):
    def __init__(self, name: str = "local", script: str = "", timeout: float = 600.0) -> None:
        super().__init__(name, script, timeout=timeout)


class CodexWorker(CliWorker):
    def __init__(self, name: str = "codex", timeout: float = 600.0, extra_args: list[str] | None = None) -> None:
        command = ["codex", "exec", "--skip-git-repo-check", "--sandbox", "workspace-write", *(extra_args or []), "{prompt}"]
        super().__init__(name, command, timeout=timeout, binary="codex")


class VibeWorker(CliWorker):
    def __init__(self, name: str = "vibe", timeout: float = 600.0, extra_args: list[str] | None = None) -> None:
        command = ["vibe", *(extra_args or []), "{prompt}"]
        super().__init__(name, command, timeout=timeout, binary="vibe")


class HermesWorker(CliWorker):
    def __init__(self, name: str = "hermes", timeout: float = 600.0, extra_args: list[str] | None = None) -> None:
        command = ["hermes", "chat", "--ephemeral", *(extra_args or []), "{prompt}"]
        super().__init__(name, command, timeout=timeout, binary="hermes")


_DEFAULT_WORKERS: dict[str, type[WorkerAdapter]] = {
    "codex": CodexWorker,
    "vibe": VibeWorker,
    "hermes": HermesWorker,
    "local": LocalScriptWorker,
}


def create_worker(name: str, config: dict[str, Any]) -> WorkerAdapter:
    config = dict(config or {})
    kind = str(config.get("type", name)).lower()
    timeout = float(config.get("timeout", 600.0))
    if kind == "script":
        script = config.get("script")
        if not script:
            raise WorkerError(f"worker '{name}': script worker requires a 'script' field")
        return ScriptWorker(name, str(script), timeout=timeout)
    if kind == "cli":
        command = config.get("command")
        if not command:
            raise WorkerError(f"worker '{name}': cli worker requires a 'command' list")
        return CliWorker(name, [str(part) for part in command], timeout=timeout)
    if kind in _DEFAULT_WORKERS:
        return _DEFAULT_WORKERS[kind](name=name, timeout=timeout, **{k: v for k, v in config.items() if k in ("extra_args",)})
    raise WorkerError(f"worker '{name}': unknown worker type '{kind}'")
