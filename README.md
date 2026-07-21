# Handler

Handler is the provider-neutral experiment and research orchestration layer for CarlosDanger projects.

It implements a bounded Hyra-style loop:

```text
objective
  -> retrieve project context and prior experience from Memorycore
  -> generate competing hypotheses
  -> execute each hypothesis in an isolated Git worktree or container
  -> evaluate results with deterministic project-owned metrics
  -> record artifacts, failures, scores, and reusable lessons
  -> require approval before merging or promoting knowledge
```

## Repository boundary

Handler owns orchestration only:

- campaign definitions and budgets;
- hypothesis and experiment queues;
- worker adapters for Codex, Mistral Vibe, Hermes, and local models;
- isolated worktree/container execution;
- deterministic evaluator adapters;
- Memorycore experiment-ledger integration;
- plateau, timeout, and resource-limit controls.

Handler does not own:

- canonical shared memory storage — Memorycore;
- human dashboards and approval UI — Omni Core;
- base-language design — MojoLisp/codex69;
- downstream compatibility logic — MojoLink/vibecheck;
- production security operations — cybersec-swarm.

## First vertical slice

The first campaign will optimize Memorycore duplicate detection using:

1. a fixed duplicate/correction benchmark;
2. one Codex proposal worker;
3. one Mistral Vibe proposal worker;
4. isolated Git worktrees;
5. pytest-based deterministic evaluation;
6. experiment and experience records written through Memorycore;
7. mandatory human approval before merge.

## Planned structure

```text
handler/
  campaigns/
  workers/
  sandboxes/
  evaluators/
  memorycore/
  policies/
  artifacts/
  cli/
tests/
docs/
```

## Safety invariants

- Workers never edit the primary checkout.
- Evaluators are independent from proposal workers.
- Protected paths cannot be modified by a campaign.
- A single successful experiment cannot become validated procedural memory.
- Production deployment, security-sensitive changes, and merges require explicit approval.
