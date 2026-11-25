import pytest

from handler.memorycore.ledger import JsonlLedger, LedgerError, create_ledger
from handler.models import Evaluation, Experiment, ExperimentStatus, Hypothesis


def _experiment(campaign_id: str = "camp", score: float = 0.5, status: str | None = None) -> Experiment:
    exp = Experiment(campaign_id=campaign_id, hypothesis=Hypothesis(statement="normalize duplicates before comparing"))
    exp.evaluation = Evaluation(experiment_id=exp.experiment_id, ok=True, score=score)
    if status:
        exp.status = status
    else:
        exp.status = ExperimentStatus.COMPLETED.value
    return exp


def test_jsonl_ledger_record_get_list(tmp_path):
    ledger = JsonlLedger(tmp_path / "ledger")
    exp = _experiment()
    ledger.record_experiment(exp)
    assert ledger.get_experiment(exp.experiment_id).to_dict() == exp.to_dict()
    assert len(ledger.list_experiments()) == 1
    assert ledger.list_experiments("other") == []
    assert ledger.get_experiment("missing") is None


def test_jsonl_ledger_approve_flips_status(tmp_path):
    ledger = JsonlLedger(tmp_path / "ledger")
    exp = _experiment()
    ledger.record_experiment(exp)
    approved = ledger.approve_experiment(exp.experiment_id, "carlos")
    assert approved.status == ExperimentStatus.APPROVED.value
    assert approved.approved_by == "carlos"
    assert ledger.get_experiment(exp.experiment_id).status == ExperimentStatus.APPROVED.value
    with pytest.raises(LedgerError):
        ledger.approve_experiment("exp_nope", "carlos")


def test_jsonl_ledger_lesson_and_context(tmp_path):
    ledger = JsonlLedger(tmp_path / "ledger")
    exp = _experiment(score=0.9)
    ledger.record_experiment(exp)
    lesson_id = ledger.record_lesson(
        campaign_id=exp.campaign_id,
        experiment_id=exp.experiment_id,
        content="Normalize before comparing duplicates.",
        approver="carlos",
    )
    assert lesson_id
    context = ledger.retrieve_context(query="duplicate normalize comparing benchmark", project_id="demo")
    assert context["count"] >= 1
    assert "normalize" in context["context_text"].lower()
    empty = ledger.retrieve_context(query="zzzz qqqq", project_id="demo")
    assert empty["count"] == 0


def test_create_ledger_factory(tmp_path):
    ledger = create_ledger({"type": "jsonl", "path": str(tmp_path / "l")})
    assert isinstance(ledger, JsonlLedger)
    with pytest.raises(LedgerError, match="unknown ledger type"):
        create_ledger({"type": "nope"})


def test_memorycore_ledger_requires_package(tmp_path):
    pytest.importorskip("memorycore", reason="memorycore not installed")
    from handler.memorycore.ledger import MemorycoreLedger

    ledger = MemorycoreLedger(tmp_path / "memorycore.db", project_id="demo")
    exp = _experiment()
    ledger.record_experiment(exp)
    found = ledger.get_experiment(exp.experiment_id)
    assert found is not None and found.status == ExperimentStatus.COMPLETED.value
    approved = ledger.approve_experiment(exp.experiment_id, "carlos")
    assert approved.status == ExperimentStatus.APPROVED.value
    assert ledger.get_experiment(exp.experiment_id).status == ExperimentStatus.APPROVED.value
    lesson = ledger.record_lesson(
        campaign_id=exp.campaign_id, experiment_id=exp.experiment_id,
        content="lesson", approver="carlos",
    )
    assert lesson
    ledger.close()


def test_memorycore_ledger_missing_package_error(tmp_path):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("memorycore"):
            raise ImportError("no memorycore")
        return real_import(name, *args, **kwargs)

    builtins.__import__ = fake_import
    try:
        with pytest.raises(LedgerError, match="memorycore"):
            create_ledger({"type": "memorycore", "database_path": str(tmp_path / "x.db")})
    finally:
        builtins.__import__ = real_import
