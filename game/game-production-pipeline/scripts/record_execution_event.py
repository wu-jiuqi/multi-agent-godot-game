#!/usr/bin/env python3
"""Record validated execution events and resume from a durable evidence ledger."""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path

from pipeline_common import canonical_digest, file_digest, load_yaml
from validate_production_charter import nonempty, number, safe_path, timestamp
from validate_execution_plan import (
    check_ref, dependencies, overlap, path_key, plan_body, plan_digest, validate_execution_plan,
)

SCHEMA = "game-production-execution-event/v1"
EVENT_TYPES = {
    "task_started", "output_recorded", "selfcheck_passed", "selfcheck_failed",
    "review_passed", "review_failed", "repair_requested", "task_completed",
    "task_failed", "takeover_requested",
}


def event_digest(event):
    return canonical_digest({k: v for k, v in event.items() if k != "event_digest"})


def request_subject(event):
    return {k: v for k, v in event.items()
            if k not in {"event_digest", "previous_event_digest", "sequence", "request_digest"}}


def read_events(path):
    if not path.exists():
        return []
    if not path.is_file():
        raise ValueError("event store is not a file")
    events = []
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            raise ValueError(f"empty/corrupt ledger record at line {index}")
        event = json.loads(line)
        if not isinstance(event, dict):
            raise ValueError(f"invalid event at line {index}")
        events.append(event)
    return events


def next_ready_tasks(plan, task_states=None, events=None):
    if events is not None and task_states is None:
        return replay_state(plan, events)["next_ready_tasks"]
    p = plan_body(plan)
    states = task_states or {
        task["task_id"]: {"status": "pending", "attempts": 0, "repairs": 0}
        for task in p["tasks"]
    }
    if isinstance(states, list):
        states = {task["task_id"]: task for task in states}
    by_id = {t["task_id"]: t for t in p["tasks"]}
    completed = {tid for tid, state in states.items() if state["status"] == "completed"}
    active = [tid for tid, state in states.items() if state["status"] in
              {"running", "produced", "checked", "reviewed"}]
    selected = []
    lane_counts = {}
    for tid in active:
        lane = by_id[tid]["lane_id"]
        lane_counts[lane] = lane_counts.get(lane, 0) + 1
    limits = {lane["lane_id"]: lane["max_parallel"] for lane in p["lanes"]}
    for task in p["tasks"]:
        tid, lane = task["task_id"], task["lane_id"]
        state = states.get(tid, {})
        if state.get("status", "pending") not in {"pending", "repairing"}:
            continue
        if not dependencies(task).issubset(completed):
            continue
        if lane_counts.get(lane, 0) >= limits[lane]:
            continue
        if any(overlap(a, b) for other in active + selected
               for a in task["write_set"] for b in by_id[other]["write_set"]):
            continue
        selected.append(tid)
        lane_counts[lane] = lane_counts.get(lane, 0) + 1
    return selected


def replay_state(plan, events, *, project_root=None):
    validation = validate_execution_plan(plan, project_root=project_root)
    if validation["errors"]:
        return {"state": "blocked", "anomalies": validation["errors"], "next_ready_tasks": [],
                "tasks": {}, "metrics": {}, "completed": []}
    p = plan_body(plan)
    tasks = {t["task_id"]: t for t in p["tasks"]}
    states = {tid: {"task_id": tid, "status": "pending", "attempts": 0, "repairs": 0,
                    "takeovers": 0, "output_digest": None} for tid in tasks}
    seen, anomalies = set(), []
    previous = None
    latest_outputs = {}
    spent = 0.0
    for index, event in enumerate(events, 1):
        if not isinstance(event, dict):
            anomalies.append(f"event {index} is not a mapping")
            break
        eid, tid, kind = event.get("event_id"), event.get("task_id"), event.get("event_type")
        error = None
        if event.get("schema_version") != SCHEMA or kind not in EVENT_TYPES:
            error = "unknown event schema/type"
        elif not nonempty(eid) or eid in seen:
            error = "missing/duplicate event_id in ledger"
        elif tid not in tasks:
            error = "unknown task"
        elif event.get("sequence") != index or event.get("previous_event_digest") != previous:
            error = "event sequence/hash-chain mismatch"
        elif event.get("event_digest") != event_digest(event):
            error = "event digest mismatch"
        elif event.get("request_digest") != canonical_digest(request_subject(event)):
            error = "event request_digest mismatch"
        elif event.get("plan_digest") != validation["plan_digest"]:
            error = "event references stale plan"
        elif not timestamp(event.get("occurred_at")) or not number(event.get("cost")):
            error = "event requires timestamp and finite nonnegative cost"
        if error:
            anomalies.append(f"{eid or index}: {error}")
            break
        seen.add(eid)
        previous = event["event_digest"]
        task, state = tasks[tid], states[tid]
        attempt, actor = event.get("attempt"), event.get("actor")
        payload = event.get("payload")
        if not isinstance(payload, dict):
            anomalies.append(f"{eid}: payload must be mapping")
            break
        review_event = kind in {"review_passed", "review_failed"}
        expected_actor = task["reviewer_role"] if review_event else task["responsible_role"]
        if actor != expected_actor:
            error = "actor does not own this operation"
        elif type(attempt) is not int:
            error = "attempt must be integer"
        elif kind == "task_started":
            # Only the next dependency- and resource-ready task may reserve execution.
            ready = next_ready_tasks(plan, states)
            limit = min(p["retry_policy"]["max_attempts"], task["self_check"]["max_repairs"] + 1)
            active_reserved = sum(tasks[x]["estimated_cost"] for x, s in states.items()
                                  if s["status"] in {"running", "produced", "checked", "reviewed"})
            if tid not in ready or attempt != state["attempts"] + 1:
                error = "task not ready or invalid attempt sequence"
            elif attempt > limit:
                error = "retry/repair budget exhausted"
            elif spent + active_reserved + task["estimated_cost"] > p["budget"]["max_cost"]:
                error = "cost budget exhausted"
            else:
                state.update(status="running", attempts=attempt, output_digest=None)
        elif attempt != state["attempts"] or attempt < 1:
            error = "event refers to wrong attempt"
        elif kind == "output_recorded":
            outputs = payload.get("outputs")
            if state["status"] != "running":
                error = "output must follow task_started"
            elif not isinstance(outputs, list):
                error = "outputs required"
            else:
                ref_errors = []
                for ref in outputs:
                    if not isinstance(ref, dict):
                        ref_errors.append("output must be mapping")
                        continue
                    check_ref({"path": ref.get("snapshot_path"), "sha256": ref.get("sha256")},
                              "immutable output snapshot", ref_errors, project_root)
                    try:
                        path_key(ref.get("path"))
                    except ValueError as exc:
                        ref_errors.append(str(exc))
                actual_paths = [ref.get("path") for ref in outputs if isinstance(ref, dict)]
                if ref_errors:
                    error = "; ".join(ref_errors)
                elif len(actual_paths) != len(set(actual_paths)) or set(map(path_key, actual_paths)) != set(map(path_key, task["output_refs"])):
                    error = "actual outputs do not match expected outputs"
                else:
                    state.update(status="produced", output_digest=canonical_digest(outputs))
                    for ref in outputs:
                        latest_outputs[path_key(ref["path"])] = (tid, ref)
        elif kind in {"selfcheck_passed", "selfcheck_failed", "review_passed", "review_failed"}:
            required_state = "checked" if review_event else "produced"
            refs = payload.get("evidence")
            ref_errors = []
            if state["status"] != required_state:
                error = "check/review out of sequence"
            elif payload.get("output_digest") != state["output_digest"]:
                error = "check/review references stale output"
            elif not isinstance(refs, list) or not refs:
                error = "actual check/review evidence required"
            else:
                for ref in refs:
                    check_ref(ref, "review/check evidence", ref_errors, project_root)
                if ref_errors:
                    error = "; ".join(ref_errors)
                elif not review_event and payload.get("command_ref") != task["self_check"]["command_ref"]:
                    error = "selfcheck command does not match plan"
                elif kind.endswith("failed") and not nonempty(payload.get("reason_code")):
                    error = "failure reason_code required"
                else:
                    state["status"] = "failed" if kind.endswith("failed") else ("reviewed" if review_event else "checked")
        elif kind == "repair_requested":
            if state["status"] != "failed" or not nonempty(payload.get("reason_code")):
                error = "repair requires failed attempt and reason"
            elif state["repairs"] >= task["self_check"]["max_repairs"] or state["attempts"] >= p["retry_policy"]["max_attempts"]:
                error = "repair budget exhausted"
            else:
                state.update(status="repairing", repairs=state["repairs"] + 1, output_digest=None)
        elif kind == "task_completed":
            if state["status"] != "reviewed" or payload.get("output_digest") != state["output_digest"]:
                error = "completion requires current independent review"
            else:
                state["status"] = "completed"
        elif kind == "task_failed":
            if state["status"] not in {"running", "produced", "checked", "reviewed"} or not nonempty(payload.get("reason_code")):
                error = "task failure requires active attempt/reason"
            else:
                state["status"] = "failed"
        elif kind == "takeover_requested":
            if state["status"] != "failed" or not nonempty(payload.get("reason_code")) or not nonempty(payload.get("recovery_ref")):
                error = "takeover requires failure, reason and recovery point"
            else:
                state.update(status="blocked", takeovers=state["takeovers"] + 1)
        if error:
            anomalies.append(f"{eid}: {error}")
            break
        spent += event["cost"]
    # Validate the current workspace only against the latest recorded version of a path.
    # Earlier attempts remain verifiable through immutable snapshots during actual repairs.
    if project_root is not None:
        active_writes = [w for tid, s in states.items() if s["status"] in {"running", "repairing"}
                         for w in tasks[tid]["write_set"]]
        for key, (tid, ref) in latest_outputs.items():
            if states[tid]["status"] in {"produced", "checked", "reviewed", "completed"} and not any(
                    overlap(key, w) for w in active_writes):
                check_ref(ref, "current output", anomalies, project_root)
    completed = [tid for tid, s in states.items() if s["status"] == "completed"]
    exhausted = [tid for tid, s in states.items() if s["status"] == "blocked" or
                 (s["status"] == "failed" and (s["attempts"] >= p["retry_policy"]["max_attempts"]
                  or s["repairs"] >= tasks[tid]["self_check"]["max_repairs"]))]
    over_budget = spent > p["budget"]["max_cost"]
    state_name = "blocked" if anomalies or exhausted or over_budget else (
        "completed" if len(completed) == len(tasks) else "running")
    ready = next_ready_tasks(plan, states) if state_name == "running" else []
    reserved = sum(tasks[tid]["estimated_cost"] for tid, s in states.items()
                   if s["status"] in {"running", "produced", "checked", "reviewed"})
    affordable = []
    for tid in ready:
        if spent + reserved + tasks[tid]["estimated_cost"] <= p["budget"]["max_cost"]:
            affordable.append(tid)
            reserved += tasks[tid]["estimated_cost"]
    if ready and not affordable and not any(s["status"] in {"running", "produced", "checked", "reviewed"}
                                           for s in states.values()):
        state_name = "blocked"
    ready = affordable
    started = sum(s["attempts"] > 0 for s in states.values())
    first = sum(s["status"] == "completed" and s["attempts"] == 1 for s in states.values())
    return {"state": state_name, "tasks": states, "completed": completed, "anomalies": anomalies,
            "next_ready_tasks": ready, "exhausted_tasks": exhausted,
            "repairable_tasks": [tid for tid, s in states.items() if s["status"] == "failed" and tid not in exhausted],
            "last_event_digest": previous, "event_count": len(seen),
            "metrics": {"first_pass_rate": first / started if started else 0,
                        "repair_count": sum(s["repairs"] for s in states.values()),
                        "takeover_count": sum(s["takeovers"] for s in states.values()),
                        "effective_completion_count": len(completed),
                        "spent_budget": spent, "budget_unit": p["budget"]["unit"],
                        "over_budget": over_budget}}


def append_event(path, event, plan, *, project_root):
    """One locked writer validates the entire proposed history before atomic replacement."""
    from validate_production_run import validate_execution_authority
    from validate_production_charter import load_approvals
    root = project_root.resolve()
    path = path.resolve()
    expected = safe_path(root, plan_body(plan)["evidence_store"]["uri"])
    if path != expected:
        raise ValueError("event store must match the plan's durable evidence_store")
    approvals, approval_errors = load_approvals(root / "game-pipeline/approvals")
    authority = validate_execution_authority(plan, project_root=root, approvals=approvals)
    if approval_errors or authority["errors"]:
        raise ValueError("; ".join(approval_errors + authority["errors"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        os.write(lock_fd, str(os.getpid()).encode("ascii"))
        history = read_events(path)
        request = request_subject(event)
        digest = canonical_digest(request)
        for previous in history:
            if previous.get("event_id") == request.get("event_id"):
                if previous.get("request_digest") != digest:
                    raise ValueError("same event_id with different payload")
                state = replay_state(plan, history, project_root=root)
                if state["anomalies"]:
                    raise ValueError("; ".join(state["anomalies"]))
                return {"state": "duplicate", "replay": state}
        record = {**request, "sequence": len(history) + 1,
                  "previous_event_digest": history[-1]["event_digest"] if history else None,
                  "request_digest": digest}
        record["event_digest"] = event_digest(record)
        proposed = history + [record]
        state = replay_state(plan, proposed, project_root=root)
        if state["anomalies"]:
            raise ValueError("; ".join(state["anomalies"]))
        # Actual cost overruns and failures remain durable facts even when they block more work.
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            for item in proposed:
                handle.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        return {"state": "appended", "event": record, "replay": state}
    finally:
        os.close(lock_fd)
        lock_path.unlink(missing_ok=True)
        # Only remove the temporary created by this writer, never a pre-existing crash artifact.
        # os.replace already removed it on success; a write error leaves it for explicit recovery.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("event", type=Path, nargs="?")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()
    try:
        plan = load_yaml(args.plan)
        root = args.project_root.resolve()
        path = safe_path(root, plan_body(plan)["evidence_store"]["uri"])
        if args.status:
            from validate_production_run import validate_execution_authority
            from validate_production_charter import load_approvals
            approvals, errors = load_approvals(root / "game-pipeline/approvals")
            authorization = validate_execution_authority(plan, project_root=root, approvals=approvals)
            if errors or authorization["errors"]:
                raise ValueError("; ".join(errors + authorization["errors"]))
            result = replay_state(plan, read_events(path), project_root=root)
        elif args.event:
            event = json.loads(args.event.read_text(encoding="utf-8")) if args.event.suffix == ".json" else load_yaml(args.event)
            result = append_event(path, event, plan, project_root=root)
        else:
            raise ValueError("provide an event file or --status")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result = {"state": "blocked", "errors": [str(exc)]}
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result.get("replay", result).get("state") not in {"blocked", "invalid"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
