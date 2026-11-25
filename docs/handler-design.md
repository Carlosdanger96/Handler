# Handler — Full Design

This document fleshes out the sketch in the [README](../README.md) into a complete,
implementable idea: a provider-neutral experiment and research orchestration layer for
CarlosDanger projects.

## 1. Vision

Handler turns a research question into a disciplined, auditable campaign. Instead of
ad-hoc "try this and see what happens", every hypothesis goes through the same bounded
loop: isolate, execute, score deterministically, record, and require human approval
before anything is merged or promoted to knowledge.

## 2. Problem statement

LLM-assisted engineering produces many proposals but few are evaluated rigorously:

- context is lost between sessions, so the same dead ends are retried;
- a single lucky success gets treated as proven knowledge;
- proposals and evaluation share code and state, so scores are not trustworthy;
- workers can touch the primary checkout, so an experiment can corrupt the repo;
- there is no record of what was tried, what failed, and why.

Handler exists to fix exactly these failure modes, and nothing more.

## 3. Design principles

- Provider-neutral: any worker that satisfies the adapter contract can participate
  (Codex, Mistral Vibe, Hermes, local models).
- Deterministic evaluation: same inputs produce the same score; evaluators are
  independent from the workers that proposed the change.
- Isolation by default: workers never write to the primary checkout.
- Append-only memory: every experiment is recorded in Memorycore; nothing is
  silently overwritten or deleted.
- Human-in-the-loop: merges, knowledge promotion, and security-sensitive changes
  require explicit approval.
- Fail closed: on ambiguity or policy violation, stop and escalate — never guess.

## 4. Core concepts

| Concept | Definition |
| --- | --- |
| Campaign | A bounded objective with a budget, an evaluator, a worker set, and policies. Example: "improve Memorycore duplicate detection". |
| Hypothesis | A testable claim, e.g. "AST-based chunking instead of raw-text chunking cuts false-positive duplicates by at least 10%". |
| Experiment | One execution of a hypothesis by one worker in one sandbox. |
| Run | The concrete execution record of an experiment: worker, sandbox commit, duration, exit status. |
| Evaluation | Deterministic scoring of an experiment's output by a project-owned evaluator. |
| Artifact | Diff, logs, metrics, and traces produced by an experiment. |
| Ledger entry | Append-only Memorycore record binding hypothesis + experiment + evaluation + artifacts + lessons. |
| Lesson | Distilled reusable knowledge. Stays a *candidate* until approved and replicated. |

## 5. The orchestration loop

```text
objective
  -> retrieve project context and prior experience from Memorycore
  -> generate competing hypotheses (one per worker, or a shared pool)
  -> schedule experiments under budget/policy constraints
  -> execute each experiment in an isolated git worktree or container
  -> evaluate results with deterministic project-owned metrics
  -> record artifacts, failures, scores, and reusable lessons in Memorycore
  -> human review
  -> approve (merge / promote knowledge) or reject (record why) or retry
```

State machine for an experiment:

```text
QUEUED -> RUNNING -> EVALUATING -> SCORED -> RECORDED -> UNDER_REVIEW
  -> APPROVED | REJECTED | RETRY -> ARCHIVED

Any state -> FAILED (recorded, budget permitting)
Campaign-level: ACTIVE -> PAUSED (plateau/timeout/budget) -> ACTIVE | CLOSED
```

## 6. Architecture

```text
handler/
  campaigns/    campaign specs (YAML), queue, budget tracking
  workers/      adapter interface + codex, vibe, hermes, local implementations
  sandboxes/    worktree and container runners, resource limits, teardown
  evaluators/   deterministic evaluator adapters (pytest, project scripts)
  memorycore/   ledger client: read context, append records, request promotion
  policies/     budget, plateau, timeout, resource-limit, protected-path checks
  artifacts/    storage layout, retention, integrity hashes
  cli/          the `handler` command
tests/
docs/
```

Data flow: `cli` -> `campaigns` -> `workers` (propose) -> `sandboxes` (execute) ->
`evaluators` (score) -> `memorycore` (record) -> `cli` (review/approve). `policies`
gates every transition; `artifacts` stores everything `memorycore` references.

## 7. Data model

All records are JSON/YAML, content-hashed, and append-only in the ledger.

Campaign spec:

```yaml
campaign:
  id: camp-memorycore-dedup-001
  objective: reduce false-positive duplicate detections in Memorycore
  target_repo: memorycore
  base_commit: <pinned sha>
  budget:
    max_experiments: 20
    max_wall_clock_minutes: 240
    max_cost_usd: 50
  workers: [codex, vibe]
  evaluator: pytest-dedup-benchmark
  policies: [plateau-5, timeout-30m, protected-paths, no-network]
  success_criteria:
    f1_improvement_over_baseline: 0.05
    min_recall: 0.95
```

Experiment record (ledger entry):

```yaml
ledger_entry:
  id: exp-0042
  campaign: camp-memorycore-dedup-001
  hypothesis: "AST-based chunking cuts false-positive duplicates >= 10%"
  worker: codex
  sandbox: {type: git-worktree, base_commit: <sha>, branch: handler/exp-0042}
  run: {started_at, finished_at, duration_s, exit_status}
  evaluation: {score, metrics: {precision, recall, f1}, passed: true}
  artifacts: [{path, sha256}]
  failures: []
  lessons: ["AST chunking removes 12% of false positives on the benchmark"]
  approvals: [{kind: merge, approver: <human>, at: <ts>}]
```

## 8. Worker adapter contract

```python
class WorkerAdapter(Protocol):
    name: str
    def propose(self, hypothesis: Hypothesis, context: Context) -> Proposal: ...
```

- `Proposal` is a machine-applicable patch (diff) plus a short rationale.
- Workers get read-only access to the primary checkout and project context.
- Workers write only inside their assigned sandbox.
- A worker that cannot produce an applicable patch returns a structured failure,
  which is recorded — it is never silently retried as a "success".

## 9. Sandbox isolation

- Default: one `git worktree` per experiment at the pinned base commit, on a unique
  branch (`handler/<experiment-id>`). Teardown removes the worktree and branch.
- Optional: ephemeral container with CPU/memory/disk limits, a hard timeout, and no
  network (or an allowlist) for stronger isolation.
- Protected paths (`.github/`, credentials, security files) are never writable by a
  campaign; a pre-merge policy check verifies the diff touches none of them.
- The primary checkout is never modified by any campaign, worker, or evaluator.

## 10. Evaluator contract

- Input: the experiment sandbox (patch applied) and the pinned benchmark/fixtures.
- Output: a deterministic score — pass/fail plus numeric metrics — and a machine
  readable report.
- Evaluators run in their own sandbox and share no code or state with the proposing
  worker.
- Non-deterministic evaluators are rejected at campaign setup.

## 11. Memorycore integration

- Read: at campaign start, retrieve project context and prior experiments/lessons
  relevant to the objective (the "prior experience" step of the loop).
- Write: append one ledger entry per experiment — hypothesis, run, evaluation,
  artifacts, failures, lessons, approvals. Nothing is edited or deleted.
- Promotion: lessons remain candidate experience. A lesson becomes validated
  procedural memory only after (a) explicit human approval and (b) replication —
  at least two independent experiments succeeding with it. A single successful
  experiment can never become validated memory.

## 12. Policies

- Budget: max experiments, max wall-clock, max cost per campaign. Exhaustion pauses
  the campaign and produces a summary, not new experiments.
- Plateau: if the best score does not improve over N consecutive experiments
  (default 5), pause and ask a human whether to continue, re-scope, or close.
- Timeout: per-experiment hard timeout; the sandbox is killed and the failure
  recorded.
- Resource limits: CPU, memory, disk, and network caps per sandbox.
- Protected paths: no campaign may modify them; violations fail closed.

## 13. Approval gates

Explicit human approval is required for:

- merging any experiment branch into the target repo's main;
- promoting a lesson to validated procedural memory;
- any change under protected paths;
- production deployment;
- security-sensitive changes (routed to cybersec-swarm review).

Every approval is recorded in the ledger entry with approver identity and timestamp.
Approvals happen in Omni Core (the human dashboard/approval UI), surfaced by Handler.

## 14. Failure modes and recovery

| Failure | Behavior |
| --- | --- |
| Worker crash / no patch | Record failure, mark experiment FAILED, continue if budget remains. |
| Evaluator crash / non-deterministic | Invalidate the score, re-run once, then escalate to a human. |
| Sandbox escape attempt | Kill sandbox, record, flag campaign for review; fail closed. |
| Budget exhausted | Stop scheduling, summarize results and open questions. |
| Conflicting hypotheses | Run both; the evaluator decides. |
| Plateau | Pause, ask human (see policies). |
| Memorycore write failure | Retry with backoff, then halt the campaign — never lose a record silently. |

## 15. CLI surface

```text
handler campaign new "<objective>" --target memorycore --evaluator pytest-dedup-benchmark
handler campaign run camp-memorycore-dedup-001 --workers codex,vibe --max-experiments 20
handler queue list
handler experiment show exp-0042
handler eval run exp-0042
handler review list
handler approve exp-0042 --kind merge
handler reject exp-0042 --reason "regresses recall"
handler artifacts open exp-0042
handler ledger tail --campaign camp-memorycore-dedup-001
```

## 16. First vertical slice

Campaign `camp-memorycore-dedup-001` — optimize Memorycore duplicate detection:

1. fixed labeled duplicate/correction benchmark as fixtures;
2. one Codex proposal worker and one Mistral Vibe proposal worker generating
   competing hypotheses;
3. isolated `git worktree` per experiment at a pinned Memorycore commit;
4. pytest-based deterministic evaluation in a separate worktree: precision, recall,
   F1, pass/fail against the benchmark;
5. every experiment appended to the Memorycore experiment ledger with artifacts and
   lessons;
6. mandatory human approval before any merge into Memorycore.

Success criteria: F1 improves over the recorded baseline by at least the configured
threshold, recall stays at or above the floor, zero evaluator errors, and everything
within budget. The slice proves the loop end to end; it deliberately uses only two
workers and one evaluator.

## 17. Safety invariants

- Workers never edit the primary checkout.
- Evaluators are independent from proposal workers.
- Protected paths cannot be modified by a campaign.
- A single successful experiment cannot become validated procedural memory.
- Production deployment, security-sensitive changes, and merges require explicit
  approval.
- All isolation is default-on; opting out requires a human decision recorded in the
  ledger.

## 18. Observability

- Every state transition emits a structured log line and appends to the ledger.
- Artifacts are content-hashed (sha256) and referenced by hash, so records are
  tamper-evident.
- `handler ledger tail` and `handler experiment show` give a full audit trail of a
  campaign: what was hypothesized, what ran, what scored, what was approved, by whom.

## 19. Roadmap

1. Phase 0 — the vertical slice above: two workers, worktree sandboxes, pytest
   evaluator, ledger writes, approval gate.
2. Phase 1 — add Hermes and local-model workers, container sandboxes, richer
   policies (cost tracking, per-worker limits), plateau auto-pause.
3. Phase 2 — multi-campaign scheduling, Omni Core dashboard/approval integration,
   lesson retrieval at campaign start via Memorycore search.
4. Phase 3 — cross-project lessons with replication tracking, promotion workflow for
   validated procedural memory.

## 20. Open questions

- Exact Memorycore ledger API shape (append endpoint, query interface, auth).
- Approval identity source: GitHub reviews, Omni Core, or both.
- Cost accounting per worker provider and how it maps to the budget.
- Lesson retrieval strategy at campaign start: tag match vs embedding search.
- Whether container sandboxes are required for the slice or Phase 1.
