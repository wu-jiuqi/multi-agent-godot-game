#!/usr/bin/env python3
"""Run the isolated, synthetic subset of the organization/prototype validation plan.

This command is deliberately not a live-project runner. It cannot prove host-wide
authorization, real MCP availability, model/token cost, or human approval.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


SCRIPT = Path(__file__).with_name("validation_sandbox.py")
SPEC = importlib.util.spec_from_file_location("validation_sandbox", SCRIPT)
assert SPEC and SPEC.loader
sandbox = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = sandbox
SPEC.loader.exec_module(sandbox)


def grant(subject: str, slot: str, *permissions: tuple[str, str], expiry: int = 200):
    return sandbox.SyntheticGrant(subject, slot, frozenset(permissions), expiry)


def run_case(case_id: str, description: str, fn: Callable[[], list[dict[str, Any]]]) -> dict[str, Any]:
    try:
        evidence = fn()
        return {"id": case_id, "description": description, "status": "pass",
                "execution_mode": "synthetic", "evidence": evidence}
    except AssertionError as exc:
        return {"id": case_id, "description": description, "status": "fail",
                "execution_mode": "synthetic", "evidence": [{"error": str(exc)}]}
    except Exception as exc:  # a harness failure is not a validation pass
        return {"id": case_id, "description": description, "status": "error",
                "execution_mode": "synthetic", "evidence": [{"error": repr(exc)}]}


def f01() -> list[dict[str, Any]]:
    org = sandbox.OrganizationSandbox()
    g = grant("planner", "slot:planning", ("spawn", "planner-1"), ("call", "brief"))
    before = sandbox.digest(org.snapshot())
    try:
        org.spawn("planner-1", g)
        raise AssertionError("unused slot unexpectedly spawned an instance")
    except sandbox.BoundaryError:
        pass
    after = sandbox.digest(org.snapshot())
    assert before == after, "rejected spawn changed protected state"
    assert not org.calls, "unused slot recorded an execution call"
    return [{"before_digest": before, "after_digest": after, "calls": org.calls,
             "audit": org.audit}]


def f06() -> list[dict[str, Any]]:
    org = sandbox.OrganizationSandbox()
    g = grant("planner", "slot:planning", ("activate", "slot:planning"),
              ("spawn", "planner-1"), ("write_fact", "scope"))
    org.activate("slot:planning", g, "planner", "planner")
    org.spawn("planner-1", g)
    org.facts["scope"] = {"owner_slot": "slot:qa", "value": "qa-review"}
    before = sandbox.digest(org.snapshot())
    try:
        org.write_fact("planner-1", "scope", "overwrite", g)
        raise AssertionError("foreign QA fact was overwritten")
    except sandbox.BoundaryError:
        pass
    after = sandbox.digest(org.snapshot())
    assert before == after, "rejected cross-domain write changed protected state"
    return [{"before_digest": before, "after_digest": after, "audit": org.audit,
             "prevention_scope": "sandbox executor only"}]


def f11() -> list[dict[str, Any]]:
    tool = sandbox.PenpotStub()
    tool.timeout_after_next_write = True
    executor = sandbox.PrototypeExecutor(tool)
    result = executor.sync({"screen:entry": {"title": "Entry"}}, {})
    node_id = result["screen:entry"]
    assert len(tool.nodes) == 1
    assert tool.nodes[node_id]["artifact_id"] == "screen:entry"
    assert any(item.get("action") == "confirmed_committed_write" for item in executor.recovery_log)
    return [{"node_id": node_id, "revision": tool.revision,
             "recovery": executor.recovery_log, "tool_audit": tool.audit}]


def f12() -> list[dict[str, Any]]:
    evidence = []
    for mode in ("disconnected", "read_only"):
        tool = sandbox.PenpotStub()
        if mode == "disconnected":
            tool.connected = False
        else:
            tool.read_only = True
        before = sandbox.digest(tool.snapshot())
        try:
            sandbox.PrototypeExecutor(tool).sync({"screen:entry": {}}, {})
            raise AssertionError(f"{mode} tool unexpectedly wrote")
        except sandbox.ToolBlocked:
            pass
        after = sandbox.digest(tool.snapshot())
        assert before == after, f"{mode} changed remote state"
        evidence.append({"mode": mode, "before_digest": before, "after_digest": after,
                         "audit": tool.audit})
    return evidence


def f13() -> list[dict[str, Any]]:
    tool = sandbox.PenpotStub()
    executor = sandbox.PrototypeExecutor(tool)
    first = executor.sync({"screen:entry": {"title": "Entry"}}, {})
    revision = tool.revision
    second = executor.sync({"screen:entry": {"title": "Entry"}}, {})
    assert first == second
    assert revision == tool.revision, "repeat created a new remote revision"
    assert len(tool.nodes) == 1, "repeat created duplicate nodes"
    return [{"first": first, "second": second, "revision": revision,
             "node_count": len(tool.nodes), "tool_audit": tool.audit}]


def build_report() -> dict[str, Any]:
    cases = [
        run_case("F01", "unused 槽位拒绝实例和调用", f01),
        run_case("F06", "禁止越权覆盖 QA 事实", f06),
        run_case("F11", "写入响应超时后读回确认", f11),
        run_case("F12", "断连与只读工具拒绝写入", f12),
        run_case("F13", "重复运行保持稳定 ID 且幂等", f13),
    ]
    return {
        "report_type": "organization-prototype-validation",
        "execution_mode": "synthetic",
        "claim_scope": "仅受控执行器的 F01/F06/F11/F12/F13 设施用例；不是 V1-V4 真实试点结论",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cases": cases,
        "v3_live": {"status": "blocked", "execution_mode": "live",
                     "reason": "未连接真实 Penpot MCP；替身证据不能升级为真实交接"},
        "v4_cost_ab": {"status": "not_run", "reason": "没有真实模型/token/费用观测；不制造成本数据"},
        "phase_results": {
            "V1": {"status": "synthetic_subset", "cases": ["F01", "F06"]},
            "V3": {"status": "blocked", "reason": "live Penpot MCP 未连接"},
            "V4": {"status": "not_run", "reason": "真实恢复与 A/B 对照未执行"},
        },
        "limitations": [
            "沙盒只约束通过其 API 的模拟执行，不能宣称拦截宿主全局调用。",
            "SyntheticGrant 不是人类批准，也不能写入正式项目 Registry。",
            "F06 prevention pass 仅适用于沙盒边界；宿主路径需另行 live 验证。",
        ],
        "overall": "pass" if all(case["status"] == "pass" for case in cases) else "fail",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="报告 JSON 输出路径；默认打印到 stdout")
    args = parser.parse_args(argv)
    report = build_report()
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0 if report["overall"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
