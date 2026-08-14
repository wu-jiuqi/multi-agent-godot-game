#!/usr/bin/env python3
"""Render deterministic Mermaid or SVG projections from Organization Registry data."""

from __future__ import annotations

import argparse
import hashlib
import html
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - environment failure
    raise SystemExit("缺少 PyYAML；请先安装插件 scripts/requirements.txt") from exc


@dataclass(frozen=True)
class ChartNode:
    stable_id: str
    title: str
    detail: str
    state: str
    group: str


@dataclass(frozen=True)
class ChartEdge:
    source: str
    target: str
    label: str


def read_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def node_key(stable_id: str) -> str:
    return "n_" + hashlib.sha256(stable_id.encode("utf-8")).hexdigest()[:14]


def mermaid_text(value: Any) -> str:
    return str(value).replace("\\", "\\\\").replace('"', "'").replace("\r", " ").replace("\n", " ").replace("[", "(").replace("]", ")")


def compact(values: list[Any], maximum: int = 2) -> str:
    texts = [str(value) for value in values if value]
    if len(texts) <= maximum:
        return "；".join(texts)
    return "；".join(texts[:maximum]) + f"；+{len(texts) - maximum}"


def _formal_graph(snapshot: dict[str, Any]) -> tuple[list[ChartNode], list[ChartEdge]]:
    formal = snapshot["formal_structure"]
    departments = {item["department_id"]: item for item in formal["departments"]}
    positions = {item["position_id"]: item for item in formal["positions"]}
    nodes: list[ChartNode] = []
    edges: list[ChartEdge] = []
    for department_id in sorted(departments):
        department = departments[department_id]
        nodes.append(ChartNode(department_id, department["display_name"], compact(department.get("responsibilities", [])), department["lifecycle"]["state"], "department"))
        if department.get("parent_department_id"):
            edges.append(ChartEdge(department["parent_department_id"], department_id, "下属部门"))
    for position_id in sorted(positions):
        position = positions[position_id]
        preset = position["preset_binding"]
        detail = f"{preset['preset_id']}@{preset['version']} | {compact(position.get('responsibilities', []))}"
        nodes.append(ChartNode(position_id, position["display_name"], detail, position["lifecycle"]["state"], position.get("department_id") or "root"))
        if position.get("department_id"):
            edges.append(ChartEdge(position["department_id"], position_id, "岗位"))
        if position.get("reports_to_position_id"):
            edges.append(ChartEdge(position_id, position["reports_to_position_id"], "汇报"))
    return nodes, sorted(edges, key=lambda item: (item.source, item.target, item.label))


def _runtime_graph(snapshot: dict[str, Any]) -> tuple[list[ChartNode], list[ChartEdge]]:
    nodes, edges = _formal_graph(snapshot)
    runtime = snapshot["runtime"]
    grants = {item["grant_id"]: item for item in runtime["temporary_grants"]}
    for grant_id in sorted(grants):
        grant = grants[grant_id]
        limits, usage = grant["limits"], grant["usage"]
        detail = f"active {usage['reserved_active_instances']}/{limits['maximum_active_instances']} | total {usage['created_instances']}/{limits['maximum_total_instances']}"
        state = "revoked" if grant.get("revoked_at") else "grant-active"
        nodes.append(ChartNode(grant_id, "临时授权", detail, state, "temporary-grants"))
        grantee = grant.get("grantee", {}).get("id")
        if grantee:
            edges.append(ChartEdge(grantee, grant_id, "授权"))
    for instance in sorted(runtime["instances"], key=lambda item: item["instance_id"]):
        instance_id = instance["instance_id"]
        kind = instance["instance_kind"]
        preset = instance["preset_binding"]
        nodes.append(ChartNode(instance_id, "正式实例" if kind == "position" else "临时实例", f"{preset['preset_id']}@{preset['version']}", instance["lifecycle"]["state"], "instances"))
        if kind == "position":
            edges.append(ChartEdge(instance["position_binding"]["position_id"], instance_id, "运行"))
        else:
            edges.append(ChartEdge(instance["temporary_binding"]["grant_id"], instance_id, "实例化"))
    return sorted(nodes, key=lambda item: item.stable_id), sorted(edges, key=lambda item: (item.source, item.target, item.label))


def _change_graph(snapshot: dict[str, Any], change_set: dict[str, Any]) -> tuple[list[ChartNode], list[ChartEdge]]:
    nodes, edges = _formal_graph(snapshot)
    by_id = {node.stable_id: node for node in nodes}
    cs_id = change_set["identity"]["change_set_id"]
    digest = change_set["integrity"]["change_set_digest"]
    nodes.append(ChartNode(cs_id, "待人工审批", f"{change_set['identity']['title']} | digest {digest[:12]}", "pending_review", "approval"))
    for operation in change_set["proposal"]["operations"]:
        target_id = operation["target_id"]
        op_type = operation["operation_type"]
        after = operation.get("after") or {}
        before = operation.get("before") or {}
        source = after if after else before
        title = source.get("display_name", target_id)
        detail = f"{op_type} | {operation.get('reason', '')}"
        state = "proposed" if op_type.startswith("create_") or op_type == "issue_temporary_grant" else "retiring" if op_type.startswith("transition_") else "changed"
        replacement = ChartNode(target_id, title, detail, state, "proposed-change")
        if target_id in by_id:
            nodes = [replacement if node.stable_id == target_id else node for node in nodes]
        else:
            nodes.append(replacement)
        edges.append(ChartEdge(cs_id, target_id, op_type))
        parent = after.get("department_id") or after.get("parent_department_id") or after.get("reports_to_position_id")
        if parent:
            edges.append(ChartEdge(parent, target_id, "提议归属"))
    return sorted(nodes, key=lambda item: item.stable_id), sorted(edges, key=lambda item: (item.source, item.target, item.label))


def _filter_scope(snapshot: dict[str, Any], view: str, scope: str, nodes: list[ChartNode], edges: list[ChartEdge], change_set_doc: dict[str, Any] | None) -> tuple[list[ChartNode], list[ChartEdge]]:
    departments = {item["department_id"]: item for item in snapshot["formal_structure"]["departments"]}
    if scope not in departments:
        raise ValueError(f"未知 Department scope: {scope}")
    scoped_departments = {scope}
    changed = True
    while changed:
        before = len(scoped_departments)
        scoped_departments.update(department_id for department_id, department in departments.items() if department.get("parent_department_id") in scoped_departments)
        changed = len(scoped_departments) != before
    allowed = set(scoped_departments)
    positions = snapshot["formal_structure"]["positions"]
    allowed.update(item["position_id"] for item in positions if item.get("department_id") in scoped_departments)
    if view == "runtime":
        grants = snapshot["runtime"]["temporary_grants"]
        allowed_grants = {item["grant_id"] for item in grants if item.get("grantee", {}).get("id") in allowed}
        allowed.update(allowed_grants)
        for instance in snapshot["runtime"]["instances"]:
            if instance["instance_kind"] == "position" and instance["position_binding"]["position_id"] in allowed:
                allowed.add(instance["instance_id"])
            if instance["instance_kind"] == "temporary" and instance["temporary_binding"]["grant_id"] in allowed_grants:
                allowed.add(instance["instance_id"])
    if view == "change" and change_set_doc is not None:
        change_set = change_set_doc["organization_change_set"]
        relevant = False
        for operation in change_set["proposal"]["operations"]:
            after = operation.get("after") or {}
            before = operation.get("before") or {}
            if operation["target_id"] in allowed or after.get("department_id") in scoped_departments or before.get("department_id") in scoped_departments:
                allowed.add(operation["target_id"])
                relevant = True
        if relevant:
            allowed.add(change_set["identity"]["change_set_id"])
    filtered_nodes = [node for node in nodes if node.stable_id in allowed]
    filtered_ids = {node.stable_id for node in filtered_nodes}
    filtered_edges = [edge for edge in edges if edge.source in filtered_ids and edge.target in filtered_ids]
    return filtered_nodes, filtered_edges


def build_graph(snapshot_doc: dict[str, Any], view: str, change_set_doc: dict[str, Any] | None = None, scope: str | None = None) -> tuple[dict[str, Any], list[ChartNode], list[ChartEdge]]:
    snapshot = snapshot_doc["organization_snapshot"]
    if view == "formal":
        nodes, edges = _formal_graph(snapshot)
    elif view == "runtime":
        nodes, edges = _runtime_graph(snapshot)
    elif view == "change":
        if change_set_doc is None:
            raise ValueError("change 视图必须提供 --change-set")
        change_set = change_set_doc["organization_change_set"]
        if change_set["identity"]["project_id"] != snapshot["identity"]["project_id"]:
            raise ValueError("Change Set 与 Snapshot project_id 不一致")
        nodes, edges = _change_graph(snapshot, change_set)
    else:  # pragma: no cover - argparse constrains this
        raise ValueError(f"未知视图: {view}")
    if scope is not None:
        nodes, edges = _filter_scope(snapshot, view, scope, nodes, edges, change_set_doc)
    metadata = {
        "view": view,
        "project_id": snapshot["identity"]["project_id"],
        "organization_revision": snapshot["identity"]["organization_revision"],
        "event_sequence": snapshot["event_watermark"]["last_event_sequence"],
        "snapshot_digest": snapshot["snapshot_integrity"]["snapshot_digest"],
        "change_set_id": None if change_set_doc is None else change_set_doc["organization_change_set"]["identity"]["change_set_id"],
        "change_set_digest": None if change_set_doc is None else change_set_doc["organization_change_set"]["integrity"]["change_set_digest"],
        "scope": scope,
    }
    known = {node.stable_id for node in nodes}
    edges = [edge for edge in edges if edge.source in known and edge.target in known]
    return metadata, sorted(nodes, key=lambda item: item.stable_id), edges


def render_mermaid(metadata: dict[str, Any], nodes: list[ChartNode], edges: list[ChartEdge]) -> str:
    lines = [
        f"%% Organization view={metadata['view']} project={metadata['project_id']} revision={metadata['organization_revision']} event_sequence={metadata['event_sequence']} scope={metadata.get('scope') or 'all'}",
        f"%% snapshot_digest={metadata['snapshot_digest']}",
    ]
    if metadata.get("change_set_id"):
        lines.append(f"%% change_set_id={metadata['change_set_id']} change_set_digest={metadata['change_set_digest']}")
    lines.append("flowchart TB")
    for node in nodes:
        label = mermaid_text(f"{node.title}\\n{node.stable_id}\\n{node.detail}")
        lines.append(f'    {node_key(node.stable_id)}["{label}"]:::{re.sub(r"[^a-zA-Z0-9_]", "_", node.state)}')
    for edge in edges:
        lines.append(f'    {node_key(edge.source)} -->|"{mermaid_text(edge.label)}"| {node_key(edge.target)}')
    styles = {
        "active": "fill:#e8f5e9,stroke:#2e7d32,color:#1b5e20",
        "suspended": "fill:#fff8e1,stroke:#f9a825,color:#6d4c00",
        "retiring": "fill:#ffebee,stroke:#c62828,color:#7f0000",
        "starting": "fill:#e3f2fd,stroke:#1565c0,color:#0d47a1",
        "draining": "fill:#fff3e0,stroke:#ef6c00,color:#7f2700",
        "grant-active": "fill:#ede7f6,stroke:#5e35b1,color:#311b92",
        "revoked": "fill:#eeeeee,stroke:#616161,color:#212121",
        "pending_review": "fill:#fffde7,stroke:#f9a825,stroke-width:3px,color:#5d4037",
        "pending-review": "fill:#fffde7,stroke:#f9a825,stroke-width:3px,color:#5d4037",
        "proposed": "fill:#e1f5fe,stroke:#0277bd,stroke-width:3px,stroke-dasharray:5 3,color:#01579b",
        "changed": "fill:#fff8e1,stroke:#ff8f00,stroke-width:3px,color:#5d4037",
    }
    for state in sorted({re.sub(r"[^a-zA-Z0-9_]", "_", node.state) for node in nodes}):
        source_state = state.replace("_", "-")
        lines.append(f"    classDef {state} {styles.get(source_state, 'fill:#fafafa,stroke:#616161,color:#212121')}")
    return "\n".join(lines) + "\n"


def render_svg(metadata: dict[str, Any], nodes: list[ChartNode], edges: list[ChartEdge]) -> str:
    width = 1200
    card_width, card_height, gap = 340, 112, 30
    columns = 3
    header_height = 120
    rows = max(1, (len(nodes) + columns - 1) // columns)
    height = header_height + rows * (card_height + gap) + 40
    positions: dict[str, tuple[float, float]] = {}
    for index, node in enumerate(nodes):
        positions[node.stable_id] = (40 + (index % columns) * (card_width + gap), header_height + (index // columns) * (card_height + gap))
    palette = {"active": ("#e8f5e9", "#2e7d32"), "suspended": ("#fff8e1", "#f9a825"), "retiring": ("#ffebee", "#c62828"), "starting": ("#e3f2fd", "#1565c0"), "draining": ("#fff3e0", "#ef6c00"), "grant-active": ("#ede7f6", "#5e35b1"), "pending_review": ("#fffde7", "#f9a825"), "proposed": ("#e1f5fe", "#0277bd"), "changed": ("#fff8e1", "#ff8f00")}
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">', '<title id="title">Organization Registry projection</title>', f'<desc id="desc">{html.escape(str(metadata))}</desc>', '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#607d8b"/></marker></defs>', '<rect width="100%" height="100%" fill="#ffffff"/>', f'<text x="40" y="36" font-family="sans-serif" font-size="22" font-weight="700">{html.escape(metadata["project_id"])} · {html.escape(metadata["view"])} view</text>', f'<text x="40" y="62" font-family="monospace" font-size="13">revision={metadata["organization_revision"]} · event={metadata["event_sequence"]} · scope={html.escape(metadata.get("scope") or "all")}</text>', f'<text x="40" y="84" font-family="monospace" font-size="11">snapshot={html.escape(metadata["snapshot_digest"])}</text>']
    if metadata.get("change_set_id"):
        out.append(f'<text x="40" y="104" font-family="monospace" font-size="11">change_set={html.escape(metadata["change_set_id"])} · {html.escape(metadata["change_set_digest"])}</text>')
    for edge in edges:
        sx, sy = positions[edge.source]
        tx, ty = positions[edge.target]
        x1, y1, x2, y2 = sx + card_width / 2, sy + card_height, tx + card_width / 2, ty
        out.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#90a4ae" stroke-width="1.5" marker-end="url(#arrow)"/>')
    for node in nodes:
        x, y = positions[node.stable_id]
        fill, stroke = palette.get(node.state, ("#fafafa", "#616161"))
        dash = ' stroke-dasharray="6 4"' if node.state == "proposed" else ""
        out.extend([f'<g id="{node_key(node.stable_id)}">', f'<rect x="{x}" y="{y}" width="{card_width}" height="{card_height}" rx="10" fill="{fill}" stroke="{stroke}" stroke-width="2"{dash}/>', f'<text x="{x + 14}" y="{y + 27}" font-family="sans-serif" font-size="16" font-weight="700">{html.escape(node.title)}</text>', f'<text x="{x + 14}" y="{y + 51}" font-family="monospace" font-size="10">{html.escape(node.stable_id)}</text>', f'<text x="{x + 14}" y="{y + 74}" font-family="sans-serif" font-size="11">{html.escape(node.detail[:54])}</text>', f'<text x="{x + 14}" y="{y + 96}" font-family="sans-serif" font-size="11" font-weight="700">{html.escape(node.state)}</text>', '</g>'])
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--change-set", type=Path)
    parser.add_argument("--view", choices=("formal", "runtime", "change"), default="formal")
    parser.add_argument("--scope", help="可选 Department ID；只生成该部门及下属编制")
    parser.add_argument("--format", choices=("mermaid", "svg"), default="mermaid")
    parser.add_argument("--output", type=Path, help="省略时写到 stdout")
    args = parser.parse_args()
    try:
        snapshot_doc = read_yaml(args.snapshot)
        change_set_doc = read_yaml(args.change_set) if args.change_set else None
        metadata, nodes, edges = build_graph(snapshot_doc, args.view, change_set_doc, args.scope)
        rendered = render_mermaid(metadata, nodes, edges) if args.format == "mermaid" else render_svg(metadata, nodes, edges)
        if args.output:
            args.output.write_text(rendered, encoding="utf-8", newline="\n")
        else:
            sys.stdout.write(rendered)
    except (OSError, UnicodeError, yaml.YAMLError, KeyError, TypeError, ValueError) as exc:
        print(f"无法生成组织投影: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
