import json
from pathlib import Path

from handler.cli.main import main

from conftest import FIX_SCRIPT, make_campaign, write_campaign


def test_init_writes_example(tmp_path, capsys):
    target = tmp_path / "campaign.json"
    assert main(["init", str(target)]) == 0
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["campaign_id"] == "example-campaign"
    assert main(["init", str(target)]) == 1


def test_run_list_show_approve_flow(tmp_path, demo_repo, capsys):
    campaign = make_campaign(demo_repo, tmp_path, script=FIX_SCRIPT)
    campaign_path = write_campaign(tmp_path, campaign)
    ledger_dir = str(tmp_path / "ledger")

    assert main(["run", str(campaign_path)]) == 0
    run_out = json.loads(capsys.readouterr().out)
    assert run_out["best_score"] == 1.0
    exp_id = run_out["experiments"][0]["experiment_id"]
    assert run_out["experiments"][0]["status"] == "completed"

    assert main(["list", "--ledger", ledger_dir]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert listed[0]["experiment_id"] == exp_id
    assert listed[0]["status"] == "completed"

    assert main(["show", exp_id, "--ledger", ledger_dir]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["experiment_id"] == exp_id
    assert shown["evaluation"]["score"] == 1.0

    assert main(["show", "exp_missing", "--ledger", ledger_dir]) == 1

    assert main(["approve", exp_id, "--by", "carlos", "--promote-lesson", "--ledger", ledger_dir]) == 0
    approved = json.loads(capsys.readouterr().out)
    assert approved["status"] == "approved"
    assert approved["approved_by"] == "carlos"

    assert main(["list", "--ledger", ledger_dir]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert listed[0]["status"] == "approved"
    lessons = (tmp_path / "ledger" / "lessons.jsonl").read_text(encoding="utf-8").strip()
    assert exp_id in lessons


def test_run_invalid_campaign_returns_error(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"campaign_id": "x"}), encoding="utf-8")
    assert main(["run", str(bad)]) == 2
    assert "error" in capsys.readouterr().err


def test_ledger_accepts_inline_json(tmp_path, capsys):
    ledger_dir = tmp_path / "inline-ledger"
    assert main(["list", "--ledger", json.dumps({"type": "jsonl", "path": str(ledger_dir)})]) == 0
    assert json.loads(capsys.readouterr().out) == []
