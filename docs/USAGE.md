# Handler usage

Handler runs a bounded, Hyra-style experiment loop against a target git repo:

```text
objective
  -> retrieve project context and prior experience from the ledger (Memorycore or JSONL)
  -> for each hypothesis: run its worker in an isolated git worktree (or container)
  -> capture the worker's change as a unified diff
  -> reject the proposal if it touches protected paths
  -> evaluate deterministically with the project-owned evaluator (pytest benchmark)
  -> record artifacts + ledger entry (always unapproved)
  -> stop on experiment budget, wall-time budget, or plateau
  -> explicit human approval required before merge or promoting a lesson
```

## Install

```bash
pip install -e .            # core (stdlib only)
pip install -e .[test]      # adds pytest
pip install -e ../Memorycore  # optional: use the Memorycore ledger backend
```

## Quickstart

```bash
handler init my-campaign.json       # scaffold a campaign definition
$EDITOR my-campaign.json            # point target_repo at your repo, define hypotheses/workers
handler run my-campaign.json        # run the loop
handler list --ledger artifacts/ledger
handler show exp_xxxxxxxxxxxx --ledger artifacts/ledger
handler approve exp_xxxxxxxxxxxx --by carlos --promote-lesson --ledger artifacts/ledger
```

Or from Python:

```python
from handler.campaigns.runner import CampaignRunner

runner = CampaignRunner.from_file("my-campaign.json")
report = runner.run()
for exp in report.experiments:
    print(exp.experiment_id, exp.status, exp.evaluation.score if exp.evaluation else None)
runner.approve(exp.experiment_id, approver="carlos", promote_lesson=True)
```

## Campaign definition (JSON)

| Field | Required | Meaning |
| --- | --- | --- |
| `campaign_id` | yes | unique campaign identifier |
| `objective` | yes | natural-language objective; used for ledger context retrieval |
| `project_id` | yes | Memorycore project id for context/ledger |
| `target_repo` | yes | path to the git repo experiments run against |
| `base_ref` | no (HEAD) | ref each sandbox worktree is created from |
| `hypotheses` | yes | list of `{ "statement": ..., "worker": <name> }` |
| `workers` | yes | map of worker name -> adapter config (see below) |
| `evaluator` | no | `{"type": "pytest", "test_paths": ["tests"], "timeout": 300}` |
| `sandbox` | no | `{"type": "worktree"}` or `{"type": "container", "image": "python:3.12-slim"}` |
| `budget` | no | `max_experiments`, `max_wall_seconds`, `per_experiment_timeout_seconds`, `plateau_limit` |
| `protected_paths` | no | glob list; proposals touching these are rejected (defaults include `.github/**`, `.env*`, `secrets/**`) |
| `ledger` | no | `{"type": "jsonl", "path": "artifacts/ledger"}` or `{"type": "memorycore", "database_path": "memorycore.db"}` |
| `artifacts_dir` | no (artifacts) | where per-experiment artifacts are written |

### Worker adapter configs

- `{ "type": "codex" }` — runs the `codex` CLI in the sandbox (fails gracefully if not installed)
- `{ "type": "vibe" }` — runs the `vibe` CLI
- `{ "type": "hermes" }` — runs the `hermes` CLI
- `{ "type": "cli", "command": ["my-tool", "{prompt}"] }` — arbitrary command; `{prompt}`, `{sandbox_path}`, `{scratch_path}` placeholders
- `{ "type": "script", "script": "...python..." }` — runs a Python script in the sandbox (deterministic; used for tests and offline demos)

## Safety invariants

- Workers only ever run inside a sandbox worktree/container; the primary checkout is never edited by a campaign.
- Proposals that modify protected paths are rejected before evaluation.
- Evaluators run as a separate step from proposal workers.
- Experiment records are written as unapproved; a single successful experiment cannot become validated procedural memory — only `handler approve --promote-lesson` (a human action) records a lesson.
- Merging, production deployment, and security-sensitive changes are out of scope for the runner and require explicit approval outside it.

## Artifacts layout

```text
artifacts/
  <campaign_id>/<experiment_id>/
    proposal.patch     # unified diff produced by the worker
    worker.log         # worker stdout/stderr
    evaluation.json    # deterministic metrics, score, pass/fail
    experiment.json    # full experiment record
    manifest.json      # index of the above
  ledger/
    experiments.jsonl  # one experiment record per line
    lessons.jsonl      # approved lessons
```
