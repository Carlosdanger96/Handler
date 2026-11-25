"""Core data model for Handler campaigns, hypotheses, experiments, and results."""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class ExperimentStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"
    APPROVED = "approved"


@dataclass
class Budget:
    max_experiments: int = 8
    max_wall_seconds: float = 3600.0
    per_experiment_timeout_seconds: float = 600.0
    plateau_limit: int = 3

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "Budget":
        data = dict(data or {})
        for key in ("max_wall_seconds", "per_experiment_timeout_seconds"):
            if key in data:
                data[key] = float(data[key])
        for key in ("max_experiments", "plateau_limit"):
            if key in data:
                data[key] = int(data[key])
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class Hypothesis:
    statement: str
    worker: str = "local"
    hypothesis_id: str = field(default_factory=lambda: new_id("hyp"))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Hypothesis":
        return cls(
            statement=str(data["statement"]),
            worker=str(data.get("worker", "local")),
            hypothesis_id=str(data.get("hypothesis_id") or new_id("hyp")),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass
class Proposal:
    hypothesis_id: str
    worker: str
    patch: str
    summary: str = ""
    proposal_id: str = field(default_factory=lambda: new_id("prop"))
    created_at: str = field(default_factory=utcnow)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Proposal":
        return cls(
            hypothesis_id=str(data["hypothesis_id"]),
            worker=str(data["worker"]),
            patch=str(data.get("patch", "")),
            summary=str(data.get("summary", "")),
            proposal_id=str(data.get("proposal_id") or new_id("prop")),
            created_at=str(data.get("created_at") or utcnow()),
        )


@dataclass
class Evaluation:
    experiment_id: str
    ok: bool
    score: float
    metrics: dict[str, Any] = field(default_factory=dict)
    passed: int = 0
    failed: int = 0
    duration_seconds: float = 0.0
    log: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Evaluation":
        return cls(
            experiment_id=str(data["experiment_id"]),
            ok=bool(data["ok"]),
            score=float(data["score"]),
            metrics=dict(data.get("metrics") or {}),
            passed=int(data.get("passed", 0)),
            failed=int(data.get("failed", 0)),
            duration_seconds=float(data.get("duration_seconds", 0.0)),
            log=str(data.get("log", "")),
        )


@dataclass
class Experiment:
    campaign_id: str
    hypothesis: Hypothesis
    experiment_id: str = field(default_factory=lambda: new_id("exp"))
    status: str = ExperimentStatus.QUEUED.value
    proposal: Proposal | None = None
    evaluation: Evaluation | None = None
    artifacts: dict[str, str] = field(default_factory=dict)
    error: str | None = None
    rejection_reasons: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utcnow)
    approved_by: str | None = None
    approved_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Experiment":
        proposal = data.get("proposal")
        evaluation = data.get("evaluation")
        return cls(
            campaign_id=str(data["campaign_id"]),
            hypothesis=Hypothesis.from_dict(data["hypothesis"]),
            experiment_id=str(data.get("experiment_id") or new_id("exp")),
            status=str(data.get("status", ExperimentStatus.QUEUED.value)),
            proposal=Proposal.from_dict(proposal) if proposal else None,
            evaluation=Evaluation.from_dict(evaluation) if evaluation else None,
            artifacts=dict(data.get("artifacts") or {}),
            error=data.get("error"),
            rejection_reasons=list(data.get("rejection_reasons") or []),
            created_at=str(data.get("created_at") or utcnow()),
            approved_by=data.get("approved_by"),
            approved_at=data.get("approved_at"),
        )


@dataclass
class Campaign:
    campaign_id: str
    objective: str
    project_id: str
    target_repo: str
    base_ref: str = "HEAD"
    hypotheses: list[Hypothesis] = field(default_factory=list)
    workers: dict[str, dict[str, Any]] = field(default_factory=dict)
    evaluator: dict[str, Any] = field(default_factory=lambda: {"type": "pytest"})
    sandbox: dict[str, Any] = field(default_factory=lambda: {"type": "worktree"})
    budget: Budget = field(default_factory=Budget)
    protected_paths: list[str] = field(default_factory=list)
    ledger: dict[str, Any] = field(default_factory=lambda: {"type": "jsonl", "path": "artifacts/ledger"})
    artifacts_dir: str = "artifacts"

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "objective": self.objective,
            "project_id": self.project_id,
            "target_repo": self.target_repo,
            "base_ref": self.base_ref,
            "hypotheses": [h.to_dict() for h in self.hypotheses],
            "workers": self.workers,
            "evaluator": self.evaluator,
            "sandbox": self.sandbox,
            "budget": self.budget.to_dict(),
            "protected_paths": self.protected_paths,
            "ledger": self.ledger,
            "artifacts_dir": self.artifacts_dir,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Campaign":
        for required in ("campaign_id", "objective", "project_id", "target_repo"):
            if not str(data.get(required) or "").strip():
                raise ValueError(f"campaign field '{required}' is required")
        hypotheses = [Hypothesis.from_dict(h) for h in data.get("hypotheses") or []]
        if not hypotheses:
            raise ValueError("campaign requires at least one hypothesis")
        workers = dict(data.get("workers") or {})
        if not workers:
            raise ValueError("campaign requires at least one worker definition")
        known = {h.worker for h in hypotheses}
        missing = known - set(workers)
        if missing:
            raise ValueError(f"hypotheses reference undefined workers: {sorted(missing)}")
        return cls(
            campaign_id=str(data["campaign_id"]),
            objective=str(data["objective"]),
            project_id=str(data["project_id"]),
            target_repo=str(data["target_repo"]),
            base_ref=str(data.get("base_ref", "HEAD")),
            hypotheses=hypotheses,
            workers=workers,
            evaluator=dict(data.get("evaluator") or {"type": "pytest"}),
            sandbox=dict(data.get("sandbox") or {"type": "worktree"}),
            budget=Budget.from_dict(data.get("budget")),
            protected_paths=list(data.get("protected_paths") or []),
            ledger=dict(data.get("ledger") or {"type": "jsonl", "path": "artifacts/ledger"}),
            artifacts_dir=str(data.get("artifacts_dir", "artifacts")),
        )
