#!/usr/bin/env python3
"""Read-only validation of project instances (not templates or live Penpot state).

Direction approval binds semantic inputs, independent of generated evidence. Review
and readiness approval bind evidence_subject_digest. subject_digest covers the final
record, including approval receipts. No digest or approval is written by this tool.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import re
from pathlib import Path
from typing import Any

import yaml

from pipeline_common import PROJECT_ID_RE, canonical_digest, file_digest, load_yaml
from validate_execution_plan import validate_tool_registry
from validate_production_charter import approval_matches, safe_path, timestamp

SCHEMA = "game-production-product-prototype-handoff/v1"
CANONICALIZATION = "product-prototype-handoff-canonical-json-v1"
DIRECTION_CANONICALIZATION = "product-prototype-direction-canonical-json-v1"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
SLOTS = {"slot:" + s for s in ("planning", "art", "programming", "audio", "qa", "tools")}
PERMISSIONS = {"read:penpot", "write:penpot", "capture:penpot"}


def body(document: dict) -> dict:
    value = document.get("product_prototype_handoff")
    if not isinstance(value, dict):
        raise ValueError("product_prototype_handoff must be a mapping")
    return value


def direction_subject(document: dict) -> dict:
    h = body(document)
    identity = h.get("identity", {})
    product = copy.deepcopy(h.get("product_identity", {}))
    for item in product.values():
        if isinstance(item, dict):
            item.pop("status", None)
            item.pop("decision_ref", None)
    packet = h.get("product_packet", {})
    scope = copy.deepcopy(packet.get("scope"))
    if isinstance(scope, dict):
        scope.pop("status", None)
        scope.pop("decision_ref", None)
    return {
        "schema_version": h.get("schema_version"),
        "handoff_id": identity.get("handoff_id"),
        "project_id": identity.get("project_id"),
        "authority": h.get("authority"),
        "direction_source_refs": [r for r in h.get("source_document_refs", [])
                                  if isinstance(r, dict) and r.get("role") != "evidence"],
        "product_identity": product,
        "product_packet": {k: packet.get(k) for k in
                           ("audience", "player_value", "design_pillars", "core_loop_ref")},
        "scope": scope,
        "prototype_intent": h.get("prototype_intent"),
    }


def handoff_digests(document: dict) -> dict[str, str]:
    h = body(document)
    direction = canonical_digest(direction_subject(document))
    penpot = copy.deepcopy(h.get("penpot", {}))
    penpot.pop("handoff_status", None)
    evidence = canonical_digest({
        "direction_subject_digest": direction,
        "source_document_refs": h.get("source_document_refs"),
        "consultation": h.get("consultation"),
        "product_document_refs": {k: h.get("product_packet", {}).get(k)
                                  for k in ("prd_ref", "gdd_ref")},
        "penpot": penpot,
    })
    subject = copy.deepcopy(h)
    subject.pop("integrity", None)
    return {"direction_subject_digest": direction,
            "evidence_subject_digest": evidence,
            "subject_digest": canonical_digest(subject)}


def _validate(document: Any, *, project_root: Path, allow_synthetic: bool,
              require_ready: bool) -> dict:
    errors: list[str] = []
    warnings = ["Local evidence checks only; Penpot remote existence, tool execution and visual quality are not verified.",
                "Approval files are checked for consistency; human identity/authenticity requires the trusted approval recorder."]
    checked_files: list[str] = []
    visited: set[int] = set()

    def walk(value, label="document", depth=0):
        if depth > 80:
            errors.append(f"{label}: nesting exceeds limit")
            return
        if isinstance(value, (dict, list)):
            if id(value) in visited:
                errors.append(f"{label}: cyclic input")
                return
            visited.add(id(value))
            if isinstance(value, dict):
                for key, item in value.items():
                    if not isinstance(key, str):
                        errors.append(f"{label}: keys must be strings")
                    else:
                        walk(item, f"{label}.{key}", depth + 1)
            else:
                for index, item in enumerate(value):
                    walk(item, f"{label}[{index}]", depth + 1)
            visited.remove(id(value))
        elif isinstance(value, str):
            if re.search(r"<[^>]+>", value):
                errors.append(f"{label}: unfilled template placeholder")
        elif value is not None and type(value) not in (int, float, bool):
            errors.append(f"{label}: non-JSON value")
        elif isinstance(value, float) and not math.isfinite(value):
            errors.append(f"{label}: non-finite number")

    walk(document)
    if errors:
        return {"state": "invalid", "errors": errors, "warnings": warnings,
                "local_evidence_ready": False, "remote_verified": False, "production_ready": False}

    def mapping(value, label):
        if not isinstance(value, dict):
            errors.append(f"{label}: must be a mapping")
            return {}
        return value

    def array(value, label):
        if not isinstance(value, list):
            errors.append(f"{label}: must be an array")
            return []
        return value

    def string(value, label):
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{label}: must be a non-empty string")
            return ""
        return value

    def strings(value, label, nonempty=False):
        values = array(value, label)
        valid = [string(v, label) for v in values]
        if nonempty and not valid:
            errors.append(f"{label}: must not be empty")
        if len(valid) != len(set(valid)):
            errors.append(f"{label}: duplicate values")
        return valid

    def reference(value, label, load=False):
        ref = mapping(value, label)
        uri = ref.get("uri", ref.get("path"))
        digest = ref.get("sha256")
        if not isinstance(digest, str) or not SHA256.fullmatch(digest):
            errors.append(f"{label}: requires SHA-256")
        if not isinstance(uri, str) or not uri:
            errors.append(f"{label}: requires repo:// URI or project-relative path")
            return None
        try:
            path = safe_path(project_root, uri)
            if not path.is_file():
                raise ValueError("referenced file does not exist")
            if file_digest(path) != digest:
                raise ValueError("file SHA-256 mismatch")
            checked_files.append(uri)
            if load:
                doc = load_yaml(path)
                walk(doc, label)
                if doc.get("synthetic") is True and not allow_synthetic:
                    errors.append(f"{label}: synthetic evidence requires explicit opt-in")
                return doc
        except (OSError, ValueError, yaml.YAMLError) as exc:
            errors.append(f"{label}: {exc}")
        return None

    root = mapping(document, "document")
    h = mapping(root.get("product_prototype_handoff"), "product_prototype_handoff")
    synthetic = h.get("synthetic", False)
    if type(synthetic) is not bool:
        errors.append("synthetic must be boolean")
    if synthetic and not allow_synthetic:
        errors.append("synthetic fixture requires --allow-synthetic; it is not a real project approval")
    if synthetic:
        warnings.append("SYNTHETIC fixture: no real human approval, Penpot execution or production acceptance is asserted.")
    if h.get("schema_version") != SCHEMA:
        errors.append("unsupported handoff schema")
    identity = mapping(h.get("identity"), "identity")
    project_id = string(identity.get("project_id"), "identity.project_id")
    if not PROJECT_ID_RE.fullmatch(project_id):
        errors.append("invalid project_id")
    handoff_id = string(identity.get("handoff_id"), "identity.handoff_id")
    if not handoff_id.startswith(f"handoff:{project_id}:"):
        errors.append("handoff_id must be project scoped")
    for key in ("owner_position_id", "prepared_by_instance_id"):
        string(identity.get(key), f"identity.{key}")
    if type(identity.get("revision")) is not int or identity["revision"] < 1:
        errors.append("identity.revision must be a positive integer")
    if identity.get("lifecycle_state") not in {"draft", "review_pending", "approved", "blocked", "superseded"}:
        errors.append("invalid lifecycle_state")
    authority = mapping(h.get("authority"), "authority")
    owner = string(authority.get("final_decision_owner"), "authority.final_decision_owner")
    if not owner.startswith("human:") or owner == "human:" or authority.get("product_owner") != owner:
        errors.append("product/final decision owner must be the same named human")
    gate_ids = strings(authority.get("direction_gate_refs"), "authority.direction_gate_refs", True)
    if not {"GATE-0", "GATE-1"} <= set(gate_ids):
        errors.append("direction requires GATE-0 and GATE-1")
    before = strings(authority.get("approval_required_before"), "authority.approval_required_before", True)

    sources = array(h.get("source_document_refs"), "source_document_refs")
    if not sources:
        errors.append("at least one source document required")
    source_ids = []
    for index, raw in enumerate(sources):
        ref = mapping(raw, f"source_document_refs[{index}]")
        source_ids.append(string(ref.get("artifact_id"), "source artifact_id"))
        if ref.get("role") not in {"goal", "requirements", "game-design", "constraint", "identity", "ux", "visual", "evidence"}:
            errors.append("invalid source role")
        if ref.get("status") not in {"confirmed", "proposal", "hypothesis", "unknown"}:
            errors.append("invalid source status")
        reference(ref, f"source_document_refs[{index}]")
    if len(source_ids) != len(set(source_ids)):
        errors.append("duplicate source artifact_id")

    product = mapping(h.get("product_identity"), "product_identity")
    for name in ("product_name", "product_title", "slogan"):
        item = mapping(product.get(name), f"product_identity.{name}")
        string(item.get("value"), f"product_identity.{name}.value")
        if item.get("status") not in {"proposed", "confirmed", "rejected", "unknown"} or item.get("decision_owner") != owner:
            errors.append(f"product_identity.{name}: invalid status/decision owner")
    packet = mapping(h.get("product_packet"), "product_packet")
    for key in ("audience", "player_value"):
        string(packet.get(key), "product_packet." + key)
    strings(packet.get("design_pillars"), "product_packet.design_pillars", True)
    scope = mapping(packet.get("scope"), "product_packet.scope")
    for name in ("must", "should", "wont"):
        strings(scope.get(name), "scope." + name, name == "must")
    for name in ("prd_ref", "gdd_ref"):
        if packet.get(name) is not None:
            reference(packet[name], "product_packet." + name)
    if not packet.get("prd_ref") and not packet.get("gdd_ref"):
        errors.append("at least one PRD/GDD document reference required")
    intent = mapping(h.get("prototype_intent"), "prototype_intent")
    string(intent.get("purpose"), "prototype_intent.purpose")
    strings(intent.get("success_criteria"), "prototype_intent.success_criteria", True)
    screen_ids = strings(intent.get("key_screen_ids"), "prototype_intent.key_screen_ids", True)
    flow_ids = strings(intent.get("flow_ids"), "prototype_intent.flow_ids", True)
    required_states = strings(intent.get("required_states"), "prototype_intent.required_states", True)
    review_owners = mapping(intent.get("review_owners"), "prototype_intent.review_owners")
    for role in ("product", "ui_ux", "art"):
        string(review_owners.get(role), "prototype_intent.review_owners." + role)

    consultation = mapping(h.get("consultation"), "consultation")
    if consultation.get("topology") != "project-manager-led-p2p":
        errors.append("invalid consultation topology")
    participants = array(consultation.get("participants"), "consultation.participants")
    participant_ids = []
    blocked_participants = False
    for raw in participants:
        p = mapping(raw, "participant")
        participant_ids.append(string(p.get("slot_id"), "participant.slot_id"))
        if p.get("activation") == "not_requested":
            if p.get("manager_instance_id") is not None:
                errors.append("inactive slot cannot have a manager instance")
            string(p.get("reason"), "inactive reason")
        elif p.get("activation") in {"active", "blocked", "requested"}:
            if p.get("status") == "responded":
                string(p.get("manager_instance_id"), "active manager instance")
                reference(p.get("response_ref"), "participant response")
            elif p.get("status") in {"blocked", "not_applicable"}:
                string(p.get("reason"), "participant reason")
                blocked_participants |= p.get("status") == "blocked"
            else:
                blocked_participants = True
        else:
            errors.append("invalid participant activation")
    if set(participant_ids) != SLOTS or len(participant_ids) != 6:
        errors.append("participants must cover exactly six unique slots")

    penpot = mapping(h.get("penpot"), "penpot")
    requested = penpot.get("requested")
    if type(requested) is not bool:
        errors.append("penpot.requested must be boolean")
    status = penpot.get("handoff_status")
    if status not in {"not_requested", "draft", "review_pending", "implementation_ready", "blocked"}:
        errors.append("invalid Penpot handoff_status")
    ready = status == "implementation_ready"
    if ready and not requested:
        errors.append("implementation_ready requires Penpot requested")
    if ready and blocked_participants:
        errors.append("blocked/pending consultation cannot be implementation_ready")
    if require_ready and not ready:
        errors.append("implementation_ready required")

    digests = handoff_digests(document)
    integrity = mapping(h.get("integrity"), "integrity")
    if integrity.get("canonicalization") != CANONICALIZATION or integrity.get("digest_algorithm") != "sha256":
        errors.append("invalid handoff canonicalization")
    if integrity.get("direction_canonicalization") != DIRECTION_CANONICALIZATION:
        errors.append("invalid direction canonicalization")
    for name, digest in digests.items():
        if integrity.get(name) != digest:
            errors.append(f"integrity.{name}: digest mismatch")

    gate = mapping(h.get("human_gate"), "human_gate")
    if gate.get("required") is not True:
        errors.append("human Gate cannot be disabled")
    if gate.get("status") not in {"pending", "approved", "rejected", "stale"}:
        errors.append("invalid human_gate.status")

    def approval(ref, label, kind, digest):
        doc = reference(ref, label, load=True)
        item = doc.get("approval") if isinstance(doc, dict) else None
        if not approval_matches(item, handoff_id, digest, owner, kind):
            errors.append(f"{label}: missing/mismatched external human approval")
            return {}
        if not allow_synthetic and item.get("evidence", {}).get("source_ref", "").startswith("fixture://"):
            errors.append(f"{label}: fixture approval cannot authorize a real project")
        if not string(item.get("approval_id"), label + ".approval_id"):
            return {}
        return item

    if requested or gate.get("status") == "approved" or identity.get("lifecycle_state") == "approved":
        if gate.get("status") != "approved" or gate.get("approval_subject_digest") != digests["direction_subject_digest"]:
            errors.append("direction Gate status/digest is absent or stale")
        record = approval(gate.get("approval_ref"), "direction approval", "product-prototype-direction", digests["direction_subject_digest"])
        approved_gates = strings(record.get("gate_refs", []), "approval.gate_refs")
        if not set(gate_ids) <= set(approved_gates):
            errors.append("external direction approval does not cover required Gates")

    if requested:
        if penpot.get("tool_id") != "tool:penpot-mcp":
            errors.append("Penpot must bind tool:penpot-mcp")
        scopes = strings(penpot.get("approved_scope"), "penpot.approved_scope", True)
        caps = strings(penpot.get("required_capabilities"), "penpot.required_capabilities", True)
        if not PERMISSIONS <= set(scopes):
            errors.append("Penpot requires read/write/capture permissions")
        registry = reference(penpot.get("tool_registry_ref"), "tool registry", load=True)
        if registry is not None:
            result = validate_tool_registry(registry, project_root=project_root)
            errors.extend("tool registry: " + e for e in result["errors"])
            registered = registry.get("tool_registry", {}).get("tools", [])
            tool = next((t for t in registered if isinstance(t, dict) and t.get("tool_id") == "tool:penpot-mcp"), {})
            if set(scopes) - set(tool.get("permission_scope", [])) or set(caps) - set(tool.get("capabilities", [])):
                errors.append("Penpot capability/permission escalation")
            if penpot.get("version") != tool.get("version"):
                errors.append("Penpot registered version mismatch")
        verification = reference(penpot.get("capability_verification_ref"), "capability verification", load=True)
        if isinstance(verification, dict):
            v = mapping(verification.get("capability_verification"), "capability_verification")
            if v.get("tool_id") != penpot.get("tool_id") or v.get("registry_sha256") != penpot.get("tool_registry_ref", {}).get("sha256"):
                errors.append("capability verification tool/registry mismatch")
            verified_caps = strings(v.get("capabilities"), "verified capabilities", True)
            if set(caps) - set(verified_caps) or v.get("status") != "passed":
                errors.append("required capabilities not verified")
        if penpot.get("input_digest") != digests["direction_subject_digest"]:
            errors.append("Penpot input_digest is stale")

    if ready or status == "review_pending":
        for key in ("file_id", "page_id", "version"):
            string(penpot.get(key), "penpot." + key)
        reference(penpot.get("file_ref"), "Penpot snapshot")
        mappings = array(penpot.get("screen_mappings"), "screen_mappings")
        mapped_ids, shape_ids = [], []
        for raw in mappings:
            item = mapping(raw, "screen mapping")
            mapped_ids.append(string(item.get("screen_id"), "mapping screen_id"))
            shape_ids.append((string(item.get("page_id"), "mapping page_id"), string(item.get("shape_id"), "mapping shape_id")))
            reference(item.get("evidence_ref"), "screen evidence")
        if set(mapped_ids) != set(screen_ids) or len(mapped_ids) != len(screen_ids) or len(shape_ids) != len(set(shape_ids)):
            errors.append("screen mapping must cover each intended screen exactly once without duplicate shapes")
        seen_flows, covered_states = [], set()
        for ref in array(penpot.get("flow_evidence_refs"), "flow_evidence_refs"):
            doc = reference(ref, "flow evidence", load=True)
            if doc is None:
                continue
            flow = mapping(doc.get("flow_evidence"), "flow_evidence")
            seen_flows.append(string(flow.get("flow_id"), "flow_id"))
            if flow.get("file_id") != penpot.get("file_id") or flow.get("input_digest") != penpot.get("input_digest"):
                errors.append("flow evidence file/input digest mismatch")
            if flow.get("result") != "passed" or not timestamp(flow.get("observed_at")):
                errors.append("flow evidence requires passed result and timestamp")
            steps = array(flow.get("steps"), "flow steps")
            if not steps:
                errors.append("flow walk requires observed steps")
            for raw in steps:
                step = mapping(raw, "flow step")
                if step.get("from_screen_id") not in screen_ids or step.get("to_screen_id") not in screen_ids:
                    errors.append("flow references unmapped screen")
                for key in ("action", "observed_result"):
                    string(step.get(key), "flow step." + key)
                covered_states.add(string(step.get("state"), "flow step.state"))
        if set(seen_flows) != set(flow_ids) or len(seen_flows) != len(flow_ids):
            errors.append("all required flows need one walkthrough evidence record")
        if not set(required_states) <= covered_states:
            errors.append("required states lack walkthrough evidence")
        for raw in array(penpot.get("unsupported_interactions"), "unsupported_interactions"):
            item = mapping(raw, "unsupported interaction")
            string(item.get("reason"), "unsupported interaction reason")
            if ready and (item.get("required") is not False or item.get("flow_id") in flow_ids):
                errors.append("required unsupported interaction prevents readiness")
        operations = reference(penpot.get("operation_evidence_ref"), "Penpot operation evidence", load=True)
        if isinstance(operations, dict):
            ops = array(operations.get("operations"), "operations")
            saw_read, saw_write, read_after_write = False, False, False
            for raw in ops:
                op = mapping(raw, "operation")
                if op.get("file_id") != penpot.get("file_id") or not timestamp(op.get("at")):
                    errors.append("operation file/timestamp mismatch")
                if op.get("kind") == "read" and op.get("result") == "passed":
                    saw_read = True
                    read_after_write |= saw_write
                elif op.get("kind") == "write":
                    if not saw_read:
                        errors.append("Penpot write occurred before read")
                    saw_write = True
                    read_after_write = False
                else:
                    errors.append("invalid operation kind/result")
            if not saw_read or not saw_write or not read_after_write:
                errors.append("read-before-write and post-write read evidence required")

    acceptance = mapping(h.get("acceptance"), "acceptance")
    if ready:
        review_roles = set()
        for raw in array(acceptance.get("professional_reviews"), "professional_reviews"):
            review = mapping(raw, "professional review")
            role = string(review.get("role"), "review role")
            review_roles.add(role)
            if role not in {"ui_ux", "art"} or review.get("reviewer") != review_owners.get(role):
                errors.append("professional reviewer does not match authorized owner")
            if review.get("reviewer") in {identity.get("owner_position_id"), identity.get("prepared_by_instance_id")}:
                errors.append("producer cannot approve its own professional review")
            if review.get("status") != "passed" or review.get("subject_digest") != digests["evidence_subject_digest"]:
                errors.append("professional review is absent or stale")
            refs = array(review.get("evidence_refs"), "review evidence_refs")
            if not refs:
                errors.append("professional review requires evidence")
            for ref in refs:
                reference(ref, "professional review evidence")
        if review_roles != {"ui_ux", "art"}:
            errors.append("readiness requires UI/UX and art reviews")
        if "penpot_implementation_ready" in before:
            approval(gate.get("handoff_approval_ref"), "readiness approval", "product-prototype-readiness", digests["evidence_subject_digest"])

    return {"state": "invalid" if errors else "valid", "project_id": project_id,
            "handoff_id": handoff_id, "synthetic": synthetic, **digests,
            "local_evidence_ready": ready and not errors,
            "remote_verified": False, "production_ready": False,
            "errors": errors, "warnings": warnings, "checked_files": sorted(set(checked_files))}


def validate_product_prototype_handoff(document: Any, *, project_root: Path,
                                      allow_synthetic: bool = False,
                                      require_ready: bool = False) -> dict:
    """Validate real values and disk evidence; never execute tools or write approvals."""
    try:
        return _validate(document, project_root=Path(project_root).resolve(),
                         allow_synthetic=allow_synthetic, require_ready=require_ready)
    except (TypeError, ValueError, AttributeError, KeyError, RecursionError, OSError, yaml.YAMLError) as exc:
        return {"state": "invalid", "errors": ["malformed handoff: " + str(exc)],
                "warnings": [], "local_evidence_ready": False,
                "remote_verified": False, "production_ready": False}


# Explicit aliases make the instance API easy to compose with the existing
# organization-extension validator without treating a template as an instance.
def handoff_direction_subject(document: dict) -> dict:
    return direction_subject(document)


def handoff_digests_for_instance(document: dict) -> dict[str, str]:
    return handoff_digests(document)


def validate_handoff_instance(document: Any, **kwargs) -> dict:
    return validate_product_prototype_handoff(document, **kwargs)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("handoff", type=Path)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--allow-synthetic", action="store_true")
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()
    try:
        result = validate_product_prototype_handoff(load_yaml(args.handoff), project_root=args.project_root,
                                                  allow_synthetic=args.allow_synthetic, require_ready=args.require_ready)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        result = {"state": "invalid", "errors": [str(exc)], "local_evidence_ready": False,
                  "remote_verified": False, "production_ready": False}
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result["state"] == "valid" else 2


if __name__ == "__main__":
    raise SystemExit(main())
