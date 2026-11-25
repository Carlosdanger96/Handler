"""`handler` CLI: run campaigns, inspect experiments, approve results."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from ..campaigns.loader import load_campaign
from ..campaigns.runner import CampaignRunner
from ..memorycore.ledger import Ledger, LedgerError, create_ledger

EXAMPLE_CAMPAIGN = {
    "campaign_id": "example-campaign",
    "objective": "Improve the target project on its deterministic benchmark without regressions.",
    "project_id": "example-project",
    "target_repo": ".",
    "base_ref": "HEAD",
    "sandbox": {"type": "worktree"},
    "evaluator": {"type": "pytest", "test_paths": ["tests"], "timeout": 300},
    "budget": {
        "max_experiments": 4,
        "max_wall_seconds": 1800,
        "per_experiment_timeout_seconds": 300,
        "plateau_limit": 2,
    },
    "protected_paths": [".github/**", ".env*", "secrets/**"],
    "ledger": {"type": "jsonl", "path": "artifacts/ledger"},
    "artifacts_dir": "artifacts",
    "workers": {
        "local": {
            "type": "script",
            "script": "from pathlib import Path\n# edit files in the sandbox to test the hypothesis\n",
        }
    },
    "hypotheses": [
        {"statement": "Describe the hypothesis the worker should test.", "worker": "local"}
    ],
}


def _resolve_ledger(spec: str | None, *, project_id: str = "handler") -> Ledger:
    if spec is None:
        return create_ledger({"type": "jsonl", "path": "artifacts/ledger"}, project_id=project_id)
    spec = spec.strip()
    if spec.startswith("{"):
        config = json.loads(spec)
    elif Path(spec).is_file():
        text = Path(spec).read_text(encoding="utf-8").strip()
        config = json.loads(text) if text.startswith("{") else {"type": "jsonl", "path": spec}
    else:
        config = {"type": "jsonl", "path": spec}
    return create_ledger(config, project_id=project_id)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="handler", description="Provider-neutral experiment orchestration layer")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run a campaign definition")
    run.add_argument("campaign", help="path to a campaign JSON file")
    run.add_argument("--max-experiments", type=int, default=None, help="override the campaign experiment budget")

    init = sub.add_parser("init", help="write an example campaign definition")
    init.add_argument("path", help="destination file for the example campaign JSON")

    list_cmd = sub.add_parser("list", help="list recorded experiments")
    list_cmd.add_argument("--ledger", default=None, help="ledger spec: JSON object, JSON file, or JSONL dir")
    list_cmd.add_argument("--campaign", default=None, help="filter by campaign id")
    list_cmd.add_argument("--project-id", default="handler")

    show = sub.add_parser("show", help="show one experiment record")
    show.add_argument("experiment_id")
    show.add_argument("--ledger", default=None)
    show.add_argument("--project-id", default="handler")

    approve = sub.add_parser("approve", help="approve an experiment (required before merge/promotion)")
    approve.add_argument("experiment_id")
    approve.add_argument("--by", required=True, help="approver identity")
    approve.add_argument("--promote-lesson", action="store_true", help="record the result as a reusable lesson")
    approve.add_argument("--ledger", default=None)
    approve.add_argument("--project-id", default="handler")
    return parser


def _cmd_run(args: argparse.Namespace) -> int:
    campaign = load_campaign(args.campaign)
    if args.max_experiments is not None:
        campaign.budget.max_experiments = args.max_experiments
    runner = CampaignRunner(campaign)
    report = runner.run()
    print(json.dumps({
        "campaign_id": report.campaign_id,
        "stopped_reason": report.stopped_reason,
        "best_score": report.best_score,
        "experiments": [
            {
                "experiment_id": e.experiment_id,
                "status": e.status,
                "worker": e.hypothesis.worker,
                "score": e.evaluation.score if e.evaluation else None,
                "ok": e.evaluation.ok if e.evaluation else None,
                "error": e.error,
                "rejection_reasons": e.rejection_reasons,
            }
            for e in report.experiments
        ],
    }, indent=2))
    pending = runner.pending_approval()
    if pending:
        print(f"\n{len(pending)} experiment(s) await approval: "
              + ", ".join(e.experiment_id for e in pending), file=sys.stderr)
    return 0


def _cmd_init(args: argparse.Namespace) -> int:
    destination = Path(args.path)
    if destination.exists():
        print(f"refusing to overwrite existing file: {destination}", file=sys.stderr)
        return 1
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(EXAMPLE_CAMPAIGN, indent=2) + "\n", encoding="utf-8")
    print(f"wrote example campaign to {destination}")
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    ledger = _resolve_ledger(args.ledger, project_id=args.project_id)
    experiments = ledger.list_experiments(args.campaign)
    print(json.dumps([{
        "experiment_id": e.experiment_id,
        "campaign_id": e.campaign_id,
        "status": e.status,
        "worker": e.hypothesis.worker,
        "statement": e.hypothesis.statement,
        "score": e.evaluation.score if e.evaluation else None,
        "approved_by": e.approved_by,
    } for e in experiments], indent=2))
    return 0


def _cmd_show(args: argparse.Namespace) -> int:
    ledger = _resolve_ledger(args.ledger, project_id=args.project_id)
    experiment = ledger.get_experiment(args.experiment_id)
    if experiment is None:
        print(f"experiment not found: {args.experiment_id}", file=sys.stderr)
        return 1
    print(json.dumps(experiment.to_dict(), indent=2))
    return 0


def _cmd_approve(args: argparse.Namespace) -> int:
    ledger = _resolve_ledger(args.ledger, project_id=args.project_id)
    try:
        experiment = ledger.approve_experiment(args.experiment_id, args.by)
    except LedgerError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.promote_lesson and experiment.evaluation is not None and experiment.evaluation.ok:
        ledger.record_lesson(
            campaign_id=experiment.campaign_id,
            experiment_id=experiment.experiment_id,
            content=(
                f"Lesson from {experiment.campaign_id}/{experiment.experiment_id}: "
                f"{experiment.hypothesis.statement} (score={experiment.evaluation.score})"
            ),
            approver=args.by,
        )
    print(json.dumps({
        "experiment_id": experiment.experiment_id,
        "status": experiment.status,
        "approved_by": experiment.approved_by,
        "approved_at": experiment.approved_at,
    }, indent=2))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    handlers: dict[str, Any] = {
        "run": _cmd_run,
        "init": _cmd_init,
        "list": _cmd_list,
        "show": _cmd_show,
        "approve": _cmd_approve,
    }
    try:
        return handlers[args.command](args)
    except (LedgerError, ValueError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
