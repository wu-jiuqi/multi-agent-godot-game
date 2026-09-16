# Autonomous production protocol

## Launch and authority

The owner and Agents co-design the project before launch. Keep the confirmed Project Brief, exact approval records, approved organization/presets/bindings, and production-charter.yaml in the project. The charter authorizes permitted actions, relative write paths, tool permissions, model/provider/version keys, total budget, a plan_budgets map keyed by stable plan ID, retries, delegated reviewers and notification rules. Plan allocations must sum to at most the total budget. Changes outside this envelope return as a batched owner decision; routine repairs stay internal.

This protocol is a Codex workflow with validators and durable records. It is not a daemon, tool interceptor, OS sandbox, billing service or cryptographic identity system. Role labels and approval source references must truthfully describe actual actors and conversations. Reported cost is entered from actual usage; validators cannot discover unreported provider charges.

## Prepare and register

1. Read the confirmed charter and validate the whole project.
2. Register real tools in game-pipeline/execution/tools.yaml using contracts/tool-registry.template.yaml: provider, version, capabilities, permissions, determinism, rollback and a local source/config/documentation snapshot with SHA-256. Recompute registry_digest using validate_execution_plan.registry_digest. Bind the exact registry file hash in the charter.
3. Build contracts/execution-plan.template.yaml with pinned context input files, model configuration source_ref and digest, tool binding subset, task responsibilities, distinct reviewers, write sets, all-join dependencies, lanes, per-attempt estimated cost, self-check command and repair cap. Select generate / automate / takeover / decide explicitly. Decision/takeover modes require a bounded decision_scope.
4. Keep generated assets under real Specialist Asset Contracts with provenance and rights; do not treat model output as rights clearance.
5. Register the plan at game-pipeline/execution/plans/<name>.yaml. Assign an existing launch budget allocation. Record its immutable plan_digest using validate_execution_plan.plan_digest. Production evidence uses exactly one JSONL ledger per plan; duplicating a plan ID or ledger is rejected.
6. Run the following from the plugin source directory, replacing paths:

~~~powershell
python scripts/validate_project_instance.py --project-root <project>
python scripts/validate_production_charter.py <project>/game-pipeline/project-definition/production-charter.yaml --project-root <project> --approval-dir <project>/game-pipeline/approvals --require-launch
python scripts/validate_production_run.py <plan.yaml> --project-root <project>
python scripts/record_execution_event.py <plan.yaml> --project-root <project> --status
~~~

Sample contracts are synthetic schemas, not production authorization. Replace every example and recalculate all affected digests before use.

## Dispatch, check, repair

The director obtains next_ready_tasks from ledger replay, dispatches actual tools/Agents only for those tasks and registers each real instance in the organization Registry. DAG dependencies, explicit all-joins, lane capacity and overlapping writes bound parallel work. Do not start an invisible worker or change a shared contract behind its consumers.

Create an event JSON/YAML and append through record_execution_event.py <plan> <event> --project-root <project>. Each request has schema_version game-production-execution-event/v1, event_id, plan_digest, task_id, event_type, actual actor, attempt, timezone timestamp, incremental cost (no double counting) and payload. The recorder adds sequence/hash-chain fields; never hand-edit the ledger.

Legal success path:
- task_started: next attempt only, empty payload; reserve estimated cost before executing.
- output_recorded: payload.outputs lists {path, sha256, snapshot_path} for exactly the declared outputs. Copy output bytes to an immutable project-relative snapshot first. Keep a different snapshot for every changed version. The current output remains at path; history verifies snapshot_path.
- selfcheck_passed: run the declared check, save its actual output, record command_ref, output_digest and evidence [{path,sha256}].
- review_passed: a distinct declared reviewer actually examines the work; record output_digest and evidence.
- task_completed: record the same current output_digest only after both checks.

output_digest is canonical_digest of the complete outputs array, including snapshot_path. Evidence reports also need immutable attempt-specific paths. Do not overwrite old check reports on a retry.

On failed checks use selfcheck_failed or review_failed with reason_code and actual evidence. Tool failures use task_failed with reason_code. Then repair_requested names the failure; start the next attempt, actually repair, and repeat checks/review. No unconditional pass and no completion based merely on a command being dispatched. Exhausted retry/cost limits block more production. A takeover_requested event includes reason_code and recovery_ref; it reports the need for a separately authorized recovery, not successful takeover.

## Recovery and verification

Re-run --status after interruption. It validates current inputs, sources, authority, chain and evidence before returning tasks, next legal dispatches, repairable/exhausted tasks and metrics. Preserve plan IDs, ledgers and cost history. A changed plan/context needs a reconciled successor with remaining budget; never overwrite an in-flight plan or delete its ledger to reset counters.

Writes use one exclusive writer lock and atomic replacement. A leftover .lock or .tmp after a process crash requires checking that the writer has exited and reconciling the last valid ledger; no automatic deletion or truncation of uncertain history. No unfinished task becomes completed on restart. Archive immutable inputs/evidence if source files will change in later phases.

Metrics expose first_pass_rate, repair_count, takeover_count, effective_completion_count and spent_budget. They are observations of recorded events, not proof of overall product quality.

## Delegated gates and delivery

For GATE-2/GATE-3/D4, the actual independent reviewer writes contracts/production-gate-decision.template.yaml. Bind charter_digest, exact subject digest, producer/reviewer, timestamp and one real evidence-backed result per launch acceptance criterion. Run evaluate_production_gate.py <decision> --project-root <project>. It returns pass / revise / blocked / awaiting_human and writes no approval.

D4 also needs all existing art requirements. Attach the receipt as publication.gate_decision_ref {path,sha256}; use subject.kind art-direction to avoid a circular file hash. Initial D2 remains an actual owner choice made during inception. A receipt never overrides missing benchmark, rights, QA or stale direction.

A GATE-4 external action needs a specific startup grant with destination, cost cap, conditions and reviewer; evaluate the exact release candidate and conditions before performing that action. The execution plan itself does not implicitly authorize publishing. Otherwise finish with a reviewable release package and one consolidated decision request.
