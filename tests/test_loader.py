import json
from pathlib import Path

import pytest

from handler.campaigns.loader import campaign_from_dict, load_campaign
from handler.models import Budget, Campaign

from conftest import REPO_ROOT, make_campaign


def test_load_example_campaign():
    campaign = load_campaign(REPO_ROOT / "examples" / "campaigns" / "duplicate_detection.json")
    assert isinstance(campaign, Campaign)
    assert campaign.campaign_id == "memorycore-duplicate-detection-v1"
    assert len(campaign.hypotheses) == 3
    assert set(campaign.workers) == {"codex", "vibe", "local"}
    assert campaign.budget.max_experiments == 4
    assert campaign.sandbox["type"] == "worktree"


def test_missing_required_field():
    data = make_campaign(Path("/tmp/x"), Path("/tmp/y"))
    del data["objective"]
    with pytest.raises(ValueError, match="objective"):
        campaign_from_dict(data)


def test_hypothesis_references_unknown_worker():
    data = make_campaign(Path("/tmp/x"), Path("/tmp/y"))
    data["hypotheses"][0]["worker"] = "ghost"
    with pytest.raises(ValueError, match="undefined workers"):
        campaign_from_dict(data)


def test_budget_defaults_and_overrides():
    budget = Budget.from_dict({"max_experiments": "5", "plateau_limit": 1})
    assert budget.max_experiments == 5
    assert budget.plateau_limit == 1
    assert budget.max_wall_seconds == 3600.0
    assert Budget.from_dict(None) == Budget()


def test_campaign_roundtrip(tmp_path):
    data = make_campaign(tmp_path / "repo", tmp_path)
    campaign = campaign_from_dict(json.loads(json.dumps(data)))
    assert campaign.to_dict()["campaign_id"] == data["campaign_id"]
    assert campaign.hypotheses[0].worker == "local"
