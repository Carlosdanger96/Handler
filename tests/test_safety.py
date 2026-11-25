from handler.policies.safety import (
    DEFAULT_PROTECTED_PATHS,
    BudgetTracker,
    ProtectedPathsPolicy,
    patch_files,
)
from handler.models import Budget, Evaluation, Experiment, ExperimentStatus, Hypothesis

PATCH = """diff --git a/src/app.py b/src/app.py
index 111..222 100644
--- a/src/app.py
+++ b/src/app.py
@@ -1 +1 @@
-old
+new
diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml
index 333..444 100644
--- a/.github/workflows/ci.yml
+++ b/.github/workflows/ci.yml
@@ -1 +1 @@
-a
+b
"""


def test_patch_files_extracts_paths():
    assert patch_files(PATCH) == ["src/app.py", ".github/workflows/ci.yml"]
    assert patch_files("") == []


def test_protected_paths_policy_flags():
    policy = ProtectedPathsPolicy([".github/**"])
    assert policy.violations(PATCH) == [".github/workflows/ci.yml"]
    assert policy.violations("diff --git a/src/app.py b/src/app.py\n+++ b/src/app.py\n") == []


def test_default_protected_paths_cover_secrets_and_env():
    policy = ProtectedPathsPolicy(None)
    patch = (
        "diff --git a/.env b/.env\n+++ b/.env\n"
        "diff --git a/secrets/key.pem b/secrets/key.pem\n+++ b/secrets/key.pem\n"
        "diff --git a/src/ok.py b/src/ok.py\n+++ b/src/ok.py\n"
    )
    assert policy.violations(patch) == [".env", "secrets/key.pem"]
    assert ".github/**" in DEFAULT_PROTECTED_PATHS


def _experiment(score: float | None) -> Experiment:
    exp = Experiment(campaign_id="c", hypothesis=Hypothesis(statement="s"))
    if score is not None:
        exp.evaluation = Evaluation(experiment_id=exp.experiment_id, ok=True, score=score)
        exp.status = ExperimentStatus.COMPLETED.value
    return exp


def test_budget_tracker_experiment_limit():
    tracker = BudgetTracker(Budget(max_experiments=2, plateau_limit=0), clock=_fake_clock())
    assert tracker.should_stop() == (False, "")
    tracker.record(_experiment(0.5))
    assert tracker.should_stop() == (False, "")
    tracker.record(_experiment(0.5))
    stop, reason = tracker.should_stop()
    assert stop and "budget" in reason


def test_budget_tracker_plateau():
    tracker = BudgetTracker(Budget(max_experiments=10, plateau_limit=2), clock=_fake_clock())
    tracker.record(_experiment(0.5))
    tracker.record(_experiment(0.5))
    assert tracker.should_stop() == (False, "")
    tracker.record(_experiment(0.4))
    stop, reason = tracker.should_stop()
    assert stop and "plateau" in reason


def test_budget_tracker_improvement_resets_plateau():
    tracker = BudgetTracker(Budget(max_experiments=10, plateau_limit=2), clock=_fake_clock())
    tracker.record(_experiment(0.5))
    tracker.record(_experiment(0.5))
    tracker.record(_experiment(0.9))
    assert tracker.plateau_count == 0
    assert tracker.best_score == 0.9


def test_budget_tracker_wall_time():
    times = iter([0.0, 100.0, 100.0, 100.0])
    tracker = BudgetTracker(Budget(max_experiments=10, max_wall_seconds=50, plateau_limit=0), clock=lambda: next(times))
    tracker.record(_experiment(0.1))
    stop, reason = tracker.should_stop()
    assert stop and "wall-time" in reason


def _fake_clock():
    return lambda: 0.0
