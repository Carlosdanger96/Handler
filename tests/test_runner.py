import json
from pathlib import Path

from handler.campaigns.runner import CampaignRunner
from handler.models import Campaign, ExperimentStatus

from conftest import (
    EVIL_SCRIPT,
    FAILING_SCRIPT,
    FIX_SCRIPT,
    NOOP_SCRIPT,
    git,
    make_campaign,
)


def _runner(tmp_path: Path, repo: Path, **kwargs) -> CampaignRunner:
    return CampaignRunner(Campaign.from_dict(make_campaign(repo, tmp_path, **kwargs)))


def test_run_completes_and_scores_perfectly(tmp_path, demo_repo):
    runner = _runner(tmp_path, demo_repo)
    report = runner.run()
    assert len(report.experiments) == 1
    exp = report.experiments[0]
    assert exp.status == ExperimentStatus.COMPLETED.value
    assert exp.evaluation is not None and exp.evaluation.ok
    assert exp.evaluation.score == 1.0
    assert exp.evaluation.passed == 2 and exp.evaluation.failed == 0
    assert report.best_score == 1.0
    assert exp.proposal is not None and "dedupe.py" in exp.proposal.patch


def test_primary_checkout_and_worktrees_untouched(tmp_path, demo_repo):
    runner = _runner(tmp_path, demo_repo)
    runner.run()
    assert git(demo_repo, "status", "--porcelain") == ""
    worktrees = git(demo_repo, "worktree", "list")
    assert "handler-wt-" not in worktrees
    assert git(demo_repo, "branch", "--list", "handler/*") == ""
    assert (demo_repo / "dedupe.py").read_text(encoding="utf-8").count("strip") == 0


def test_artifacts_and_ledger_written(tmp_path, demo_repo):
    runner = _runner(tmp_path, demo_repo)
    report = runner.run()
    exp = report.experiments[0]
    artifact_dir = tmp_path / "artifacts" / "test-campaign" / exp.experiment_id
    for name in ("proposal.patch", "worker.log", "evaluation.json", "experiment.json", "manifest.json"):
        assert (artifact_dir / name).is_file(), name
    evaluation = json.loads((artifact_dir / "evaluation.json").read_text(encoding="utf-8"))
    assert evaluation["score"] == 1.0
    manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["files"] and all(len(f["sha256"]) == 64 for f in manifest["files"])
    stored = runner.ledger.get_experiment(exp.experiment_id)
    assert stored is not None and stored.status == ExperimentStatus.COMPLETED.value


def test_approval_required_then_promotes_lesson(tmp_path, demo_repo):
    runner = _runner(tmp_path, demo_repo)
    report = runner.run()
    exp = report.experiments[0]
    assert exp.status != ExperimentStatus.APPROVED.value
    pending = runner.pending_approval()
    assert [e.experiment_id for e in pending] == [exp.experiment_id]
    approved = runner.approve(exp.experiment_id, approver="carlos", promote_lesson=True)
    assert approved.status == ExperimentStatus.APPROVED.value
    assert approved.approved_by == "carlos"
    lessons_path = tmp_path / "ledger" / "lessons.jsonl"
    lessons = [json.loads(line) for line in lessons_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lessons) == 1 and lessons[0]["experiment_id"] == exp.experiment_id
    assert runner.pending_approval() == []


def test_protected_path_proposal_rejected(tmp_path, demo_repo):
    runner = _runner(tmp_path, demo_repo, script=EVIL_SCRIPT)
    report = runner.run()
    exp = report.experiments[0]
    assert exp.status == ExperimentStatus.REJECTED.value
    assert exp.evaluation is None
    assert any(".github/workflows/evil.yml" in reason for reason in exp.rejection_reasons)
    assert git(demo_repo, "status", "--porcelain") == ""


def test_worker_failure_recorded_as_failed(tmp_path, demo_repo):
    runner = _runner(tmp_path, demo_repo, script=FAILING_SCRIPT)
    report = runner.run()
    exp = report.experiments[0]
    assert exp.status == ExperimentStatus.FAILED.value
    assert exp.error and "exited 3" in exp.error


def test_experiment_budget_limits_runs(tmp_path, demo_repo):
    campaign = make_campaign(demo_repo, tmp_path, script=FIX_SCRIPT, hypotheses=3)
    campaign["budget"]["max_experiments"] = 2
    report = CampaignRunner(Campaign.from_dict(campaign)).run()
    assert len(report.experiments) == 2
    assert "budget" in report.stopped_reason


def test_plateau_stops_campaign(tmp_path, demo_repo):
    campaign = make_campaign(demo_repo, tmp_path, script=NOOP_SCRIPT, hypotheses=3)
    campaign["budget"]["plateau_limit"] = 1
    report = CampaignRunner(Campaign.from_dict(campaign)).run()
    assert len(report.experiments) == 2
    assert "plateau" in report.stopped_reason
    for exp in report.experiments:
        assert exp.status == ExperimentStatus.COMPLETED.value
        assert exp.evaluation.score == 0.5


def test_context_retrieved_from_prior_experiments(tmp_path, demo_repo):
    runner = _runner(tmp_path, demo_repo)
    runner.run()
    runner2 = _runner(tmp_path, demo_repo)
    report = runner2.run()
    assert report.experiments[0].status == ExperimentStatus.COMPLETED.value
