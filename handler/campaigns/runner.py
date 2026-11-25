"""CampaignRunner: the bounded Hyra-style orchestration loop.

objective -> retrieve context from the ledger -> run hypotheses in isolated
sandboxes -> evaluate deterministically -> record artifacts and ledger entries
-> stop on budget/plateau/timeout. Merging or promoting knowledge always
requires explicit approval; the runner never merges.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

from ..artifacts.store import ArtifactStore
from ..evaluators.base import Evaluator
from ..evaluators.pytest_eval import create_evaluator
from ..memorycore.ledger import Ledger, create_ledger
from ..models import Campaign, Experiment, ExperimentStatus, Hypothesis
from ..policies.approval import ApprovalGate
from ..policies.safety import BudgetTracker, ProtectedPathsPolicy
from ..sandboxes.base import Sandbox
from ..sandboxes.container import create_sandbox
from ..workers.base import WorkerAdapter, WorkerError
from ..workers.cli import create_worker


@dataclass
class CampaignReport:
    campaign_id: str
    objective: str
    experiments: list[Experiment] = field(default_factory=list)
    stopped_reason: str = "completed"
    best_score: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "objective": self.objective,
            "stopped_reason": self.stopped_reason,
            "best_score": self.best_score,
            "experiments": [e.to_dict() for e in self.experiments],
        }


class CampaignRunner:
    def __init__(
        self,
        campaign: Campaign,
        *,
        ledger: Ledger | None = None,
        artifact_store: ArtifactStore | None = None,
        workers: dict[str, WorkerAdapter] | None = None,
        evaluator: Evaluator | None = None,
        protected: ProtectedPathsPolicy | None = None,
        approval: ApprovalGate | None = None,
        sandbox_factory: Callable[[Experiment], Sandbox] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.campaign = campaign
        self.ledger = ledger or create_ledger(campaign.ledger, project_id=campaign.project_id)
        self.artifact_store = artifact_store or ArtifactStore(campaign.artifacts_dir)
        self.workers = workers or {name: create_worker(name, cfg) for name, cfg in campaign.workers.items()}
        self.evaluator = evaluator or create_evaluator(campaign.evaluator)
        self.protected = protected or ProtectedPathsPolicy(campaign.protected_paths or None)
        self.approval = approval or ApprovalGate(self.ledger)
        self._sandbox_factory = sandbox_factory or (
            lambda experiment: create_sandbox(
                campaign.sandbox,
                target_repo=campaign.target_repo,
                base_ref=campaign.base_ref,
                branch=f"handler/{experiment.experiment_id}",
            )
        )
        self._clock = clock

    @classmethod
    def from_file(cls, path: str | Path, **overrides: Any) -> "CampaignRunner":
        from .loader import load_campaign

        return cls(load_campaign(path), **overrides)

    def run(self) -> CampaignReport:
        campaign = self.campaign
        context = self.ledger.retrieve_context(query=campaign.objective, project_id=campaign.project_id, limit=10)
        tracker = BudgetTracker(campaign.budget, clock=self._clock)
        experiments: list[Experiment] = []
        stopped_reason = "all hypotheses evaluated"
        for hypothesis in campaign.hypotheses:
            stop, reason = tracker.should_stop()
            if stop:
                stopped_reason = reason
                break
            experiment = self._run_experiment(hypothesis, context, tracker)
            experiments.append(experiment)
            self.ledger.record_experiment(experiment)
            tracker.record(experiment)
        else:
            stop, reason = tracker.should_stop()
            if stop:
                stopped_reason = reason
        best = tracker.best_score
        return CampaignReport(
            campaign_id=campaign.campaign_id,
            objective=campaign.objective,
            experiments=experiments,
            stopped_reason=stopped_reason,
            best_score=best,
        )

    def _run_experiment(self, hypothesis: Hypothesis, context: dict[str, Any], tracker: BudgetTracker) -> Experiment:
        campaign = self.campaign
        experiment = Experiment(campaign_id=campaign.campaign_id, hypothesis=hypothesis)
        experiment.status = ExperimentStatus.RUNNING.value
        worker_log = ""
        sandbox = self._sandbox_factory(experiment)
        try:
            sandbox.prepare()
            worker = self.workers[hypothesis.worker]
            proposal, worker_log = worker.propose(
                sandbox=sandbox,
                hypothesis=hypothesis,
                campaign=campaign,
                context=context,
            )
            experiment.proposal = proposal
            violations = self.protected.violations(proposal.patch)
            if violations:
                experiment.status = ExperimentStatus.REJECTED.value
                experiment.rejection_reasons = [f"protected path modified: {path}" for path in violations]
            else:
                evaluation = self.evaluator.evaluate(sandbox=sandbox, experiment=experiment)
                experiment.evaluation = evaluation
                experiment.status = ExperimentStatus.COMPLETED.value
        except WorkerError as exc:
            experiment.status = ExperimentStatus.FAILED.value
            experiment.error = f"worker '{hypothesis.worker}': {exc}"
        except Exception as exc:
            experiment.status = ExperimentStatus.FAILED.value
            experiment.error = f"{type(exc).__name__}: {exc}"
        finally:
            experiment.artifacts = self.artifact_store.save_experiment(
                experiment,
                worker_log=worker_log,
            )
            try:
                sandbox.cleanup()
            except Exception:
                pass
        return experiment

    def approve(self, experiment_id: str, approver: str, *, promote_lesson: bool = False) -> Experiment:
        experiment = self.ledger.approve_experiment(experiment_id, approver)
        if promote_lesson and experiment.evaluation is not None and experiment.evaluation.ok:
            content = (
                f"Lesson from {experiment.campaign_id}/{experiment_id}: "
                f"{experiment.hypothesis.statement} "
                f"(score={experiment.evaluation.score}, approved by {approver})"
            )
            self.ledger.record_lesson(
                campaign_id=experiment.campaign_id,
                experiment_id=experiment_id,
                content=content,
                approver=approver,
            )
        stored = self.ledger.get_experiment(experiment_id)
        if stored is not None:
            stored.artifacts = experiment.artifacts or stored.artifacts
            self.artifact_store.save_experiment(stored)
        return experiment

    def pending_approval(self) -> list[Experiment]:
        return [
            e for e in self.ledger.list_experiments(self.campaign.campaign_id)
            if e.status not in (ExperimentStatus.APPROVED.value, ExperimentStatus.REJECTED.value)
        ]
