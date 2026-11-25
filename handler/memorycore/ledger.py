"""Experiment ledger backends.

The ledger stores experiment records and reusable lessons. Experiments are
always recorded as unapproved (pending); only an explicit
``approve_experiment`` call promotes one, so a single successful experiment
can never silently become validated procedural memory.

Backends:
- ``jsonl``: standalone append-only JSONL files (no dependencies).
- ``memorycore``: writes through the Memorycore service when it is installed.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Protocol

from ..models import Experiment, ExperimentStatus, utcnow


class LedgerError(RuntimeError):
    """Ledger backend is unavailable or a record could not be written."""


class Ledger(Protocol):
    def record_experiment(self, experiment: Experiment) -> str: ...
    def record_lesson(self, *, campaign_id: str, experiment_id: str, content: str, approver: str) -> str: ...
    def approve_experiment(self, experiment_id: str, approver: str) -> Experiment: ...
    def get_experiment(self, experiment_id: str) -> Experiment | None: ...
    def list_experiments(self, campaign_id: str | None = None) -> list[Experiment]: ...
    def retrieve_context(self, *, query: str, project_id: str, limit: int = 10) -> dict[str, Any]: ...


def _experiment_line(experiment: Experiment) -> str:
    return json.dumps(experiment.to_dict(), sort_keys=True)


def _append(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def _read_experiments(path: Path) -> list[Experiment]:
    if not path.is_file():
        return []
    experiments: list[Experiment] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        experiments.append(Experiment.from_dict(json.loads(line)))
    return experiments


def _rewrite(path: Path, experiments: list[Experiment]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for experiment in experiments:
            handle.write(_experiment_line(experiment) + "\n")


class JsonlLedger:
    """Standalone JSONL ledger: experiments.jsonl plus lessons.jsonl."""

    def __init__(self, path: str | Path) -> None:
        self.root = Path(path)
        self.experiments_path = self.root / "experiments.jsonl"
        self.lessons_path = self.root / "lessons.jsonl"

    def record_experiment(self, experiment: Experiment) -> str:
        _append(self.experiments_path, _experiment_line(experiment))
        return experiment.experiment_id

    def record_lesson(self, *, campaign_id: str, experiment_id: str, content: str, approver: str) -> str:
        lesson = {
            "lesson_id": f"les_{experiment_id.split('_', 1)[-1]}",
            "campaign_id": campaign_id,
            "experiment_id": experiment_id,
            "content": content,
            "approved_by": approver,
            "created_at": utcnow(),
        }
        _append(self.lessons_path, json.dumps(lesson, sort_keys=True))
        return lesson["lesson_id"]

    def approve_experiment(self, experiment_id: str, approver: str) -> Experiment:
        experiments = _read_experiments(self.experiments_path)
        for experiment in experiments:
            if experiment.experiment_id == experiment_id:
                if experiment.status == ExperimentStatus.APPROVED.value:
                    return experiment
                experiment.status = ExperimentStatus.APPROVED.value
                experiment.approved_by = approver
                experiment.approved_at = utcnow()
                _rewrite(self.experiments_path, experiments)
                return experiment
        raise LedgerError(f"experiment not found: {experiment_id}")

    def get_experiment(self, experiment_id: str) -> Experiment | None:
        for experiment in _read_experiments(self.experiments_path):
            if experiment.experiment_id == experiment_id:
                return experiment
        return None

    def list_experiments(self, campaign_id: str | None = None) -> list[Experiment]:
        experiments = _read_experiments(self.experiments_path)
        if campaign_id is not None:
            experiments = [e for e in experiments if e.campaign_id == campaign_id]
        return experiments

    def retrieve_context(self, *, query: str, project_id: str, limit: int = 10) -> dict[str, Any]:
        tokens = [t for t in re.split(r"\W+", query.lower()) if len(t) > 3]
        scored: list[tuple[float, Experiment]] = []
        for experiment in self.list_experiments():
            text = json.dumps(experiment.to_dict()).lower()
            score = float(sum(text.count(token) for token in tokens))
            if score > 0:
                scored.append((score, experiment))
        scored.sort(key=lambda item: item[0], reverse=True)
        top = [experiment for _, experiment in scored[:limit]]
        context_text = "\n".join(
            f"- [{e.status}] {e.hypothesis.statement} (score={e.evaluation.score if e.evaluation else 'n/a'})"
            for e in top
        )
        return {
            "project_id": project_id,
            "query": query,
            "count": len(top),
            "experiments": [e.to_dict() for e in top],
            "context_text": context_text or "(no prior experience recorded)",
        }


class MemorycoreLedger:
    """Writes experiment records through the Memorycore service.

    Experiments are stored as ``note`` memories in ``pending`` status, tagged
    for Handler; approval flips them to ``active``. Lessons become
    ``procedure`` memories only on explicit approval.
    """

    def __init__(self, database_path: str | Path, project_id: str) -> None:
        try:
            from memorycore.memory_service import MemoryService
        except ImportError as exc:
            raise LedgerError(
                "memorycore ledger requires the memorycore package (pip install -e ../Memorycore)"
            ) from exc
        self.project_id = project_id
        self.service = MemoryService(database_path)

    def close(self) -> None:
        self.service.close()

    def _tags(self, campaign_id: str) -> list[str]:
        return ["handler", "experiment", campaign_id]

    def record_experiment(self, experiment: Experiment) -> str:
        memory = self.service.add_memory(
            project_id=self.project_id,
            memory_type="note",
            content=f"experiment {experiment.experiment_id} ({experiment.campaign_id}): {experiment.hypothesis.statement}",
            summary=f"handler experiment {experiment.status}",
            tags=self._tags(experiment.campaign_id),
            created_by="handler",
            metadata={"kind": "experiment", "experiment": experiment.to_dict()},
            source_type="system_event",
            source_uri=f"handler://experiments/{experiment.experiment_id}",
            status="pending",
        )
        return memory.id

    def record_lesson(self, *, campaign_id: str, experiment_id: str, content: str, approver: str) -> str:
        memory = self.service.add_memory(
            project_id=self.project_id,
            memory_type="procedure",
            content=content,
            summary=f"handler lesson from {experiment_id}",
            tags=["handler", "lesson", campaign_id],
            created_by=approver,
            metadata={"kind": "lesson", "campaign_id": campaign_id, "experiment_id": experiment_id},
            source_type="system_event",
            source_uri=f"handler://lessons/{experiment_id}",
            status="active",
        )
        return memory.id

    def approve_experiment(self, experiment_id: str, approver: str) -> Experiment:
        matches = self.service.search_memory(
            query=f"handler experiment {experiment_id}",
            project_id=self.project_id,
            limit=10,
            status="pending",
        )
        target = None
        for memory in matches:
            experiment_data = (memory.metadata or {}).get("experiment") or {}
            if experiment_data.get("experiment_id") == experiment_id:
                target = memory
                break
        if target is None:
            raise LedgerError(f"experiment not found in memorycore: {experiment_id}")
        self.service.approve_memory(target.id, approved_by=approver)
        experiment = Experiment.from_dict((target.metadata or {})["experiment"])
        experiment.status = ExperimentStatus.APPROVED.value
        experiment.approved_by = approver
        experiment.approved_at = utcnow()
        return experiment

    def get_experiment(self, experiment_id: str) -> Experiment | None:
        for status in ("pending", "active"):
            for memory in self.service.search_memory(
                query=f"handler experiment {experiment_id}",
                project_id=self.project_id,
                limit=20,
                status=status,
            ):
                experiment_data = (memory.metadata or {}).get("experiment") or {}
                if experiment_data.get("experiment_id") == experiment_id:
                    experiment = Experiment.from_dict(experiment_data)
                    if status == "active":
                        experiment.status = ExperimentStatus.APPROVED.value
                    return experiment
        return None

    def list_experiments(self, campaign_id: str | None = None) -> list[Experiment]:
        experiments: list[Experiment] = []
        seen: set[str] = set()
        for status in ("pending", "active"):
            for memory in self.service.search_memory(
                query="handler experiment",
                project_id=self.project_id,
                limit=100,
                status=status,
            ):
                experiment_data = (memory.metadata or {}).get("experiment") or {}
                experiment_id = experiment_data.get("experiment_id")
                if not experiment_id or experiment_id in seen:
                    continue
                if campaign_id is not None and experiment_data.get("campaign_id") != campaign_id:
                    continue
                seen.add(experiment_id)
                experiment = Experiment.from_dict(experiment_data)
                if status == "active":
                    experiment.status = ExperimentStatus.APPROVED.value
                experiments.append(experiment)
        return experiments

    def retrieve_context(self, *, query: str, project_id: str, limit: int = 10) -> dict[str, Any]:
        return self.service.retrieve_context(query=query, project_id=project_id or self.project_id, limit=limit)


def create_ledger(config: dict[str, Any], *, project_id: str = "handler") -> Ledger:
    config = dict(config or {})
    kind = str(config.get("type", "jsonl")).lower()
    if kind == "jsonl":
        return JsonlLedger(config.get("path", "artifacts/ledger"))
    if kind == "memorycore":
        return MemorycoreLedger(config.get("database_path", "memorycore.db"), project_id=project_id)
    raise LedgerError(f"unknown ledger type: {kind}")
