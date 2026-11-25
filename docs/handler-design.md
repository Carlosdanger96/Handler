# Handler — Full Design (v1)

This document fleshes out the one-page sketch in `README.md` into a complete,
implementable concept. It is the reference for the first vertical slice and for
reviewing any later change to Handler's scope.

## 1. Vision

Handler is the provider-neutral experiment and research orchestration layer for
CarlosDanger projects. Instead of a human (or a single agent) manually trying
ideas one at a time, Handler runs **campaigns**: bounded, budgeted, fully
logged competitions between competing hypotheses, executed in isolation and
gated by deterministic evaluation and explicit human approval.

The unit of work is not a patch. It is an **experiment**: a hypothesis, an
isolated execution, a scored result, and a ledger record — so that every bit
of progress (including failures) becomes reusable, auditable experience in
Memorycore.

## 2. Problem statement

Today, "trying an idea" in a project means: a person or agent edits the main
checkout, runs something, eyeballs the result, and maybe remembers it. That
fails in predictable ways:

- Ideas are not compared fairly (different contexts, different machines, different moods).
- Failures are lost, so the same dead ends are re-explored.
- There is no budget discipline — one runaway worker can burn hours or dollars.
- Nothing is auditable: you cannot later answer "why did we choose X?".
- Promising changes get merged on vibes, not on deterministic evidence.

Handler exists to make experimentation **repeatable, comparable, bounded, and
approved** — without taking ownership of the projects it experiments on.

## 3. The core loop

Every campaign runs the same bounded Hyra-style loop:

```text
1. OBJECTIVE      campaign defines a measurable objective + budget
2. RETRIEVE       pull project context + prior experience from Memorycore
3. HYPOTHESIZE    one or more workers generate competing hypotheses
4. EXECUTE        each hypothesis runs in an isolated worktree or container
5. EVALUATE       independent, deterministic, project-owned metrics score it
6. RECORD         artifacts, failures, scores, lessons -> Memorycore ledger
7. GATE           human approval required before merge or knowledge promotion
```

Stage details:

1. **Objective** — a campaign spec declares the target repo, the objective
   (e.g. "reduce duplicate-detection false positives on benchmark B"), the
   benchmark/evaluator to use, the allowed workers, and the budget.
2. **Retrieve** — Handler queries the Memorycore experiment ledger for prior
   runs on the same or related objectives: what was tried, what scored, what
   lessons were recorded. New hypotheses must cite or differ from this prior
   experience.
3. **Hypothesize** — each registered worker (Codex, Mistral Vibe, Hermes,
   local model) receives the same brief (objective + retrieved context +
   constraints) and produces a hypothesis: a concrete, testable change
   proposal, not free text.
4. **Execute** — each hypothesis is applied in its own isolated Git worktree
   (or container) branched from the campaign's base commit. Workers never
   touch the primary checkout.
5. **Evaluate** — an evaluator adapter, written by the target project and
   independent from the proposal workers, runs deterministic metrics in the
   sandbox and emits a structured score. No LLM judgment in the scoring path.
6. **Record** — run metadata, diff, logs, score, evaluator version, and any
   extracted lesson are written to the Memorycore experiment ledger.
7. **Gate** — nothing merges and nothing becomes validated procedural memory
   without explicit human approval (surfaced through Omni Core). A single
   successful experiment is never promoted to knowledge on its own.

## 4. Scope and boundaries

Handler **owns**:

- campaign definitions and budgets (what to run, how much it may cost);
- hypothesis and experiment queues (ordering, dedup, scheduling);
- worker adapters for Codex, Mistral Vibe, Hermes, and local models;
- isolated worktree/container execution and resource limits;
- deterministic evaluator adapters and the scoring pipeline;
- Memorycore experiment-ledger integration (reads and writes);
- plateau, timeout, and resource-limit controls.

Handler **does not own**:

- canonical shared memory storage — Memorycore;
- human dashboards and approval UI — Omni Core;
- base-language design — MojoLisp/codex69;
- downstream compatibility logic — MojoLink/vibecheck;
- production security operations — cybersec-swarm.

Interface rule: Handler talks to these systems through narrow adapters
(`handler/memorycore/`, evaluator plugins, worker plugins). If a boundary
system changes, only its adapter changes.

## 5. Architecture

Planned structure (unchanged from the README):

```text
handler/
  campaigns/    campaign specs, queue, scheduler, budget tracking
  workers/      worker adapter interface + Codex/Vibe/Hermes/local plugins
  sandboxes/    worktree & container execution, isolation, resource limits
  evaluators/   evaluator plugin interface + runner
  memorycore/   ledger client: read prior experience, write experiment records
  policies/     approval gates, protected paths, plateau/timeout enforcement
  artifacts/    run artifacts: diffs, logs, scores, provenance; retention
  cli/          `handler` command-line entry point
tests/
docs/
```

### 5.1 Campaigns (`handler/campaigns/`)

- **Campaign spec** (versioned YAML or Python): objective, target repo +
  base commit, evaluator reference, allowed workers, protected paths,
  budget (max runs, max wall-clock, max estimated cost), stop conditions
  (plateau, timeout, budget exhaustion), approval requirements.
- **Queue**: hypotheses are deduplicated (identical briefs + identical prior
  context ⇒ one run) and scheduled FIFO with priority for cheaper workers
  first when budget is tight.
- **Budget tracker**: decrements per run; hard-stops the campaign when any
  budget dimension is exhausted. Budgets are enforced by policy, not by
  worker goodwill.

### 5.2 Workers (`handler/workers/`)

- **Adapter contract**: `propose(brief: CampaignBrief) -> Hypothesis`, where
  `Hypothesis` = {id, worker, base_commit, diff/branch ref, rationale,
  cited_prior_experience}. Workers are read-only w.r.t. the primary checkout;
  they only produce a hypothesis artifact.
- **Registry**: plugins for Codex, Mistral Vibe, Hermes, and local models.
  Each plugin handles its own auth, rate limits, and prompt formatting. New
  providers are added by implementing the same contract — Handler core never
  changes for a new provider.
- **Fairness**: every worker in a campaign gets the identical brief so
  results are comparable.

### 5.3 Sandboxes (`handler/sandboxes/`)

- Two execution backends behind one interface: `WorktreeSandbox` (Git
  worktree from the base commit) and `ContainerSandbox` (ephemeral container
  for heavier isolation).
- Isolation guarantees: no writes outside the sandbox; protected paths
  (campaign-configured) are read-only or absent; default-deny network egress
  unless the campaign explicitly allows it; CPU/memory/time limits enforced
  by the backend.
- Each run gets a fresh sandbox; nothing is reused between hypotheses except
  the read-only base checkout.

### 5.4 Evaluators (`handler/evaluators/`)

- **Contract**: `evaluate(sandbox, hypothesis) -> EvaluationResult` where
  `EvaluationResult` = {metrics: {name: value}, passed: bool, score: float,
  logs_ref, evaluator_version, deterministic: true}.
- Evaluators are **project-owned plugins** and strictly independent from the
  proposal workers — the worker that proposed a change never scores it.
- Scoring must be deterministic: same sandbox content ⇒ same metrics. The
  evaluator records its own version/hash so results are reproducible.

### 5.5 Memorycore integration (`handler/memorycore/`)

- **Read**: prior experiment records + distilled experience for the
  campaign's objective domain (used in stage 2).
- **Write**: one ledger record per run — hypothesis, worker, sandbox type,
  evaluator + version, metrics, score, pass/fail, artifact refs, extracted
  lesson, approval status.
- Handler never becomes canonical memory; it is a writer/client of
  Memorycore's experiment ledger.

### 5.6 Policies (`handler/policies/`)

- **Approval gates**: merge, knowledge promotion, deployment, and
  security-sensitive changes require explicit human approval. Handler can
  prepare everything (branch, PR draft, evidence pack) but cannot approve.
- **Protected paths**: campaign-declared paths that no campaign may modify;
  enforced at sandbox level, not by convention.
- **Plateau control**: if no run improves the best score within N consecutive
  runs (campaign-configured), the campaign pauses and asks for human
  direction instead of burning budget.
- **Timeouts**: per-stage (propose/execute/evaluate) and per-campaign
  wall-clock timeouts; timed-out runs are recorded as failures with reason.

### 5.7 Artifacts (`handler/artifacts/`)

- Per run: hypothesis JSON, diff/patch, sandbox logs, evaluator output,
  score JSON, ledger record ID. Content-addressed storage with a retention
  policy (keep all scored runs; prune raw logs after T days unless flagged).
- Provenance is first-class: every artifact links back to campaign, worker,
  evaluator versions, and base commit.

### 5.8 CLI (`handler/cli/`)

- `handler campaign new/run/status/stop` — lifecycle;
- `handler queue list` — pending/running/done hypotheses;
- `handler run show <id>` — full evidence pack for a run (for review);
- `handler approve <id>` — records human approval (writes to ledger via
  Memorycore; UI lives in Omni Core, CLI is the fallback);
- `handler ledger query --objective ...` — read prior experience.

## 6. Data model (sketch)

```text
Campaign      {id, objective, target_repo, base_commit, evaluator_ref,
               workers[], protected_paths[], budget, stop_conditions,
               status, created_at}
Hypothesis    {id, campaign_id, worker, brief_hash, diff_ref, rationale,
               cited_experience[]}
ExperimentRun {id, campaign_id, hypothesis_id, sandbox{type, limits},
               status, started_at, finished_at, timeout_reason?}
EvaluationResult {run_id, evaluator_ref, evaluator_version, metrics{},
               score, passed, logs_ref}
LedgerRecord  {run_id, hypothesis, evaluation, lesson?, approval?,
               written_to: memorycore, at}
Approval      {run_id, approver, decision, at, note?}   # required for
                                                          # merge/promotion
```

## 7. Execution and concurrency model

- Campaigns run their queue with bounded parallelism (default: 1 run at a
  time per sandbox host; configurable up to resource limits).
- Ordering: FIFO within a campaign; across campaigns, a simple fair-share
  scheduler respecting global budget caps.
- Every state transition (queued → running → evaluated → recorded →
  gated/approved/rejected) is written to the ledger before the next starts,
  so a crash mid-campaign is recoverable: on restart, Handler reattaches to
  runs in `running` state and re-evaluates or marks them timed out.

## 8. Safety invariants and how they are enforced

| Invariant | Enforcement mechanism |
|---|---|
| Workers never edit the primary checkout | hypotheses exist only as diffs/branches; execution happens in fresh worktrees/containers |
| Evaluators are independent from proposal workers | evaluator is a separate plugin, chosen per campaign, never the proposing worker |
| Protected paths cannot be modified by a campaign | enforced by the sandbox backend, verified post-run by diff inspection |
| A single successful experiment cannot become validated procedural memory | promotion requires an Approval record; one pass only reaches "candidate" |
| Deployment, security-sensitive changes, and merges require explicit approval | hard gate in the pipeline; Handler has no code path that merges or deploys |
| Budget/plateau/timeout discipline | enforced by `policies/`, not by workers |
| Default-deny network egress in sandboxes | sandbox backend default; campaigns opt in explicitly |

## 9. First vertical slice

Campaign: **improve Memorycore duplicate detection**.

1. Fixed duplicate/correction benchmark owned by the Memorycore project.
2. Two proposal workers: one Codex, one Mistral Vibe, identical briefs.
3. Each hypothesis executed in an isolated Git worktree from a pinned
   Memorycore base commit.
4. Deterministic pytest-based evaluator (project-owned, independent of both
   workers) producing precision/recall on the benchmark.
5. Every run recorded to the Memorycore experiment ledger with artifacts.
6. Winner (if any) prepared as a draft PR with the full evidence pack;
   merge only after explicit human approval.

Success criteria for the slice: both workers produce runnable hypotheses;
evaluator scores are reproducible (same run ⇒ same score); ledger contains
complete records; no merge happens without an Approval; budget caps hold
under an artificially tiny budget.

## 10. Rollout phases

1. **Phase 0 — skeleton**: `handler/cli` + campaigns queue + Memorycore
   ledger client (read/write) + artifact store. No workers yet.
2. **Phase 1 — vertical slice**: as in §9, one campaign, two workers,
   worktree sandbox, pytest evaluator, approval gate.
3. **Phase 2 — hardening**: container sandbox, more workers (Hermes, local),
   multi-campaign scheduling, plateau/timeout policies, richer ledger
   queries.
4. **Phase 3 — integration**: Omni Core dashboard/approval UI consumes the
   evidence packs; Handler remains UI-agnostic.

## 11. How we judge Handler itself

- **Comparability**: same brief ⇒ comparable runs across workers.
- **Reproducibility**: re-running an evaluator on a recorded sandbox yields
  the recorded score.
- **Budget adherence**: 100% of campaigns stop at their declared caps.
- **Traceability**: any merged change can be traced to campaign → run →
  evaluation → approval in the ledger.
- **Safety**: zero merges/promotions without Approval; zero writes to the
  primary checkout or protected paths (verified by tests and post-run
  diffs).

## 12. Risks and mitigations

- **Worker gaming the evaluator** — evaluator is independent and
  deterministic; benchmark fixtures are held out from workers.
- **Budget overruns from hanging runs** — per-stage timeouts + hard budget
  stops in `policies/`.
- **Ledger spam / noise** — dedup of identical briefs; plateau control stops
  unproductive campaigns early.
- **Sandbox escape or dirty isolation** — fresh sandbox per run,
  default-deny egress, post-run diff verification against protected paths.
- **Approval fatigue** — evidence packs are complete and one-click in Omni
  Core; CLI fallback. Approval is never skipped, only batched.
- **Vendor lock-in** — worker adapters are pluggable; no provider-specific
  logic in core.

## 13. Open questions

- Exact Memorycore ledger schema for experiment records (needs Memorycore
  owner sign-off).
- Whether the first slice's benchmark lives in the Memorycore repo or in
  Handler under `evaluators/` with a pinned version.
- Container backend choice (rootless podman vs. docker vs. firecracker) —
  decide at Phase 2; worktrees carry Phase 1.
- Global vs. per-campaign approval: does one approval cover a campaign's
  best run only, or a batch? Default: per run.
