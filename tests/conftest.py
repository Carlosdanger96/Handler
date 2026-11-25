import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

BUGGY_DEDUPE = '''def find_duplicates(items):
    seen = []
    dupes = []
    for item in items:
        if item in seen and item not in dupes:
            dupes.append(item)
        seen.append(item)
    return dupes
'''

FIXED_DEDUPE = '''def find_duplicates(items):
    seen = set()
    dupes = []
    for item in items:
        key = item.strip().lower()
        if key in seen and key not in dupes:
            dupes.append(key)
        seen.add(key)
    return dupes
'''

DEDUPE_TEST = '''from dedupe import find_duplicates


def test_case_insensitive_duplicates():
    assert find_duplicates(["Apple", "apple", "APPLE", "Banana"]) == ["apple"]


def test_no_duplicates():
    assert find_duplicates(["a", "b", "c"]) == []
'''

FIX_SCRIPT = (
    "from pathlib import Path\n"
    f"Path('dedupe.py').write_text({FIXED_DEDUPE!r}, encoding='utf-8')\n"
)

NOOP_SCRIPT = (
    "from pathlib import Path\n"
    "path = Path('dedupe.py')\n"
    "path.write_text(path.read_text(encoding='utf-8') + '\\n# noop\\n', encoding='utf-8')\n"
)

EVIL_SCRIPT = (
    "from pathlib import Path\n"
    "Path('.github/workflows/evil.yml').write_text('on: push\\n', encoding='utf-8')\n"
)

FAILING_SCRIPT = "raise SystemExit(3)\n"


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


@pytest.fixture
def demo_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "demo"
    (repo / "tests").mkdir(parents=True)
    (repo / ".github" / "workflows").mkdir(parents=True)
    (repo / "dedupe.py").write_text(BUGGY_DEDUPE, encoding="utf-8")
    (repo / "tests" / "test_dedupe.py").write_text(DEDUPE_TEST, encoding="utf-8")
    (repo / "conftest.py").write_text(
        "import sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).parent))\n",
        encoding="utf-8",
    )
    (repo / ".github" / "workflows" / "ci.yml").write_text("name: ci\n", encoding="utf-8")
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "test")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "initial")
    return repo


def make_campaign(repo: Path, tmp_path: Path, script: str = FIX_SCRIPT, hypotheses: int = 1, **overrides) -> dict:
    campaign = {
        "campaign_id": "test-campaign",
        "objective": "Make duplicate detection case-insensitive on the fixed benchmark.",
        "project_id": "demo",
        "target_repo": str(repo),
        "base_ref": "HEAD",
        "sandbox": {"type": "worktree"},
        "evaluator": {"type": "pytest", "test_paths": ["tests"], "timeout": 120},
        "budget": {"max_experiments": 8, "max_wall_seconds": 600, "per_experiment_timeout_seconds": 120, "plateau_limit": 3},
        "protected_paths": [".github/**", ".env*"],
        "ledger": {"type": "jsonl", "path": str(tmp_path / "ledger")},
        "artifacts_dir": str(tmp_path / "artifacts"),
        "workers": {"local": {"type": "script", "script": script, "timeout": 60}},
        "hypotheses": [
            {"statement": f"hypothesis {i}: normalize before comparing", "worker": "local"}
            for i in range(hypotheses)
        ],
    }
    campaign.update(overrides)
    return campaign


def write_campaign(tmp_path: Path, campaign: dict) -> Path:
    path = tmp_path / "campaign.json"
    path.write_text(json.dumps(campaign), encoding="utf-8")
    return path
