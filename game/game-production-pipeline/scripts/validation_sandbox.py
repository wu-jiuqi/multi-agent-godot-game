"""Isolated synthetic executors for organization and Penpot failure experiments.

These guards protect only operations dispatched through these objects. They are
not host-wide tool enforcement, a real registry, an approval service, or Penpot MCP.
Synthetic grants must never be exported as human approvals.
"""
from __future__ import annotations

import copy
import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Any, Callable


SLOT_IDS = frozenset(f"slot:{name}" for name in (
    "planning", "art", "programming", "audio", "qa", "tools"))


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


class BoundaryError(RuntimeError):
    """An operation was refused before the protected business mutation."""


class ToolBlocked(BoundaryError):
    pass


class WriteResponseTimeout(RuntimeError):
    """The fake remote committed a write but its response was lost."""


@dataclass(frozen=True)
class SyntheticGrant:
    subject: str
    slot_id: str
    permissions: frozenset[tuple[str, str]]
    expires_at: int
    state: str = "applied"
    approved: bool = True
    execution_mode: str = "synthetic"


class OrganizationSandbox:
    """Small in-memory executor with exact target scopes and injected clock."""

    def __init__(self, now: int = 100) -> None:
        self.now = now
        self.slots = {slot: {"status": "unused"} for slot in sorted(SLOT_IDS)}
        self.instances: dict[str, dict[str, Any]] = {}
        self.facts: dict[str, dict[str, Any]] = {}
        self.calls: list[dict[str, Any]] = []
        self.audit: list[dict[str, Any]] = []

    def snapshot(self) -> dict[str, Any]:
        return copy.deepcopy({"slots": self.slots, "instances": self.instances,
                              "facts": self.facts, "calls": self.calls})

    def _refuse(self, action: str, target: str, reason: str) -> None:
        self.audit.append({"action": action, "target": target, "outcome": "rejected",
                           "reason": reason, "time": self.now})
        raise BoundaryError(reason)

    def _authorize(self, grant: SyntheticGrant | None, action: str,
                   target: str, subject: str | None = None) -> SyntheticGrant:
        if not isinstance(grant, SyntheticGrant):
            self._refuse(action, target, "missing synthetic authorization")
        if grant.execution_mode != "synthetic" or grant.slot_id not in SLOT_IDS:
            self._refuse(action, target, "unknown slot or non-synthetic grant")
        if not grant.approved or grant.state != "applied":
            self._refuse(action, target, "approval is missing or not applied")
        if self.now >= grant.expires_at:
            self._refuse(action, target, "grant expired")
        if subject is not None and grant.subject != subject:
            self._refuse(action, target, "grant subject does not own instance")
        if (action, target) not in grant.permissions:
            self._refuse(action, target, "exact action/target scope missing")
        return grant

    def activate(self, slot_id: str, grant: SyntheticGrant | None,
                 responsibility_owner: str, acceptance_owner: str) -> None:
        if slot_id not in SLOT_IDS:
            self._refuse("activate", slot_id, "unknown slot")
        grant = self._authorize(grant, "activate", slot_id)
        if grant.slot_id != slot_id or not responsibility_owner or not acceptance_owner:
            self._refuse("activate", slot_id, "slot identity or owners invalid")
        if self.slots[slot_id]["status"] != "unused":
            self._refuse("activate", slot_id, "slot already materialized")
        self.slots[slot_id] = {"status": "active", "responsibility_owner": responsibility_owner,
                               "acceptance_owner": acceptance_owner}
        self.audit.append({"action": "activate", "target": slot_id, "outcome": "applied"})

    def merge(self, slot_id: str, target_slot: str, grant: SyntheticGrant | None,
              responsibility_owner: str, acceptance_owner: str) -> None:
        grant = self._authorize(grant, "merge", f"{slot_id}->{target_slot}")
        if (slot_id not in SLOT_IDS or target_slot not in SLOT_IDS
                or slot_id == target_slot or "slot:qa" in (slot_id, target_slot)):
            self._refuse("merge", slot_id, "invalid merge or QA independence violation")
        if grant.slot_id != slot_id or self.slots[slot_id]["status"] != "unused":
            self._refuse("merge", slot_id, "source slot invalid or already materialized")
        if self.slots[target_slot]["status"] != "active":
            self._refuse("merge", slot_id, "merge target must be active")
        if not responsibility_owner or not acceptance_owner:
            self._refuse("merge", slot_id, "merge must preserve both owners")
        self.slots[slot_id] = {"status": "merged", "target_slot": target_slot,
                               "responsibility_owner": responsibility_owner,
                               "acceptance_owner": acceptance_owner}
        self.audit.append({"action": "merge", "target": slot_id, "outcome": "applied"})

    def spawn(self, instance_id: str, grant: SyntheticGrant | None) -> None:
        grant = self._authorize(grant, "spawn", instance_id)
        if self.slots[grant.slot_id]["status"] not in {"active", "merged"}:
            self._refuse("spawn", instance_id, "unused slot cannot start an instance")
        if instance_id in self.instances:
            self._refuse("spawn", instance_id, "instance ID already exists")
        for instance in self.instances.values():
            if (instance["subject"] == grant.subject
                    and ((instance["slot_id"] == "slot:qa") != (grant.slot_id == "slot:qa"))):
                self._refuse("spawn", instance_id, "QA actor must be independent from production")
        self.instances[instance_id] = {"subject": grant.subject, "slot_id": grant.slot_id,
                                        "status": "active"}
        self.audit.append({"action": "spawn", "target": instance_id, "outcome": "applied"})

    def invoke(self, instance_id: str, target: str, grant: SyntheticGrant | None) -> None:
        instance = self.instances.get(instance_id)
        if not instance or instance["status"] != "active":
            self._refuse("call", target, "instance is missing or suspended")
        grant = self._authorize(grant, "call", target, instance["subject"])
        if grant.slot_id != instance["slot_id"]:
            self._refuse("call", target, "grant does not cover instance slot")
        if self.slots[grant.slot_id]["status"] == "unused":
            self._refuse("call", target, "unused slot cannot execute")
        self.calls.append({"instance_id": instance_id, "slot_id": grant.slot_id,
                           "target": target, "time": self.now, "execution_mode": "synthetic"})
        self.audit.append({"action": "call", "target": target, "outcome": "executed"})

    def write_fact(self, instance_id: str, fact_id: str, value: Any,
                   grant: SyntheticGrant | None) -> None:
        instance = self.instances.get(instance_id)
        if not instance or instance["status"] != "active":
            self._refuse("write_fact", fact_id, "no active instance")
        grant = self._authorize(grant, "write_fact", fact_id, instance["subject"])
        current = self.facts.get(fact_id)
        if grant.slot_id != instance["slot_id"] or not current:
            self._refuse("write_fact", fact_id, "unknown fact or instance slot mismatch")
        if current["owner_slot"] != grant.slot_id or current.get("reserved_for_human", False):
            self._refuse("write_fact", fact_id, "foreign fact/QA opinion/human budget is protected")
        current["value"] = copy.deepcopy(value)
        self.audit.append({"action": "write_fact", "target": fact_id, "outcome": "applied"})

    def reclaim_expired(self, grants: dict[str, SyntheticGrant]) -> None:
        for instance_id, instance in self.instances.items():
            grant = grants.get(instance_id)
            if grant is None or self.now >= grant.expires_at or grant.state != "applied":
                instance["status"] = "suspended"
                self.audit.append({"action": "suspend", "target": instance_id,
                                   "outcome": "applied"})


class PenpotStub:
    """An in-memory fake remote; every ID and call below is synthetic."""

    def __init__(self, file_id: str = "synthetic-file", namespace: str = "pilot") -> None:
        self.file_id, self.namespace = file_id, namespace
        self.connected = True
        self.read_only = False
        self.scopes = {("read", file_id), ("write", file_id)}
        self.capabilities = {"read", "write", "interaction"}
        self.nodes: dict[str, dict[str, Any]] = {}
        self.revision = 0
        self.audit: list[dict[str, Any]] = []
        self._receipts: dict[str, int] = {}
        self._mutations: dict[str, dict[str, Any]] = {}
        self.timeout_after_next_write = False
        self.disconnect_after_next_write = False

    def snapshot(self) -> dict[str, Any]:
        return copy.deepcopy({"file_id": self.file_id, "revision": self.revision,
                              "nodes": self.nodes, "mutations": self._mutations})

    def stable_id(self, artifact_id: str) -> str:
        return "synthetic-node-" + str(uuid.uuid5(uuid.NAMESPACE_URL,
            f"{self.file_id}/{self.namespace}/{artifact_id}"))

    def _check(self, operation: str, file_id: str) -> None:
        reason = None
        if not self.connected:
            reason = "Penpot stub disconnected"
        elif file_id != self.file_id or (operation, file_id) not in self.scopes:
            reason = "exact file scope missing"
        elif operation not in self.capabilities:
            reason = f"missing capability: {operation}"
        elif operation == "write" and self.read_only:
            reason = "Penpot stub read-only"
        if reason:
            self.audit.append({"operation": operation, "outcome": "blocked", "reason": reason})
            raise ToolBlocked(reason)

    def read(self, file_id: str) -> dict[str, Any]:
        self._check("read", file_id)
        receipt = f"read-{len(self.audit) + 1}"
        self._receipts[receipt] = self.revision
        self.audit.append({"operation": "read", "outcome": "success", "receipt": receipt,
                           "revision": self.revision})
        return {**self.snapshot(), "read_receipt": receipt}

    def upsert(self, file_id: str, artifact_id: str, kind: str, content: dict[str, Any],
               read_receipt: str, mutation_id: str) -> str:
        self._check("write", file_id)
        if read_receipt not in self._receipts or self._receipts[read_receipt] != self.revision:
            raise ToolBlocked("a current read-before-write receipt is required")
        if kind not in {"screen", "flow"} or not artifact_id or not mutation_id:
            raise ToolBlocked("artifact kind/identity is invalid")
        if kind == "flow":
            if "interaction" not in self.capabilities:
                raise ToolBlocked("missing capability: interaction")
            for endpoint in ("source", "target"):
                if content.get(endpoint) not in self.nodes:
                    raise ToolBlocked(f"unknown flow {endpoint}")
        node_id = self.stable_id(artifact_id)
        payload = {"artifact_id": artifact_id, "kind": kind,
                   "namespace": self.namespace, "content": copy.deepcopy(content)}
        payload_hash = digest(payload)
        prior = self._mutations.get(mutation_id)
        if prior:
            if prior["payload_digest"] != payload_hash:
                raise ToolBlocked("mutation ID reused with different payload")
            if self.nodes.get(node_id) != payload:
                raise ToolBlocked("prior mutation no longer matches current remote state")
            self.audit.append({"operation": "write", "outcome": "idempotent", "node_id": node_id})
            return node_id
        old = self.nodes.get(node_id)
        if old and (old.get("namespace") != self.namespace or old.get("artifact_id") != artifact_id):
            raise ToolBlocked("existing foreign node cannot be overwritten")
        if old != payload:
            self.nodes[node_id] = payload
            self.revision += 1
        self._mutations[mutation_id] = {"payload_digest": payload_hash, "node_id": node_id}
        self.audit.append({"operation": "write", "outcome": "committed", "node_id": node_id,
                           "mutation_id": mutation_id, "revision": self.revision})
        if self.timeout_after_next_write:
            self.timeout_after_next_write = False
            if self.disconnect_after_next_write:
                self.connected = False
                self.disconnect_after_next_write = False
            raise WriteResponseTimeout("synthetic write committed; response lost")
        return node_id


class PrototypeExecutor:
    """Read/verify/upsert/re-read client with bounded recovery and no blind retry."""

    def __init__(self, tool: PenpotStub) -> None:
        self.tool = tool
        self.recovery_log: list[dict[str, Any]] = []

    def _sync(self, artifact_id: str, kind: str, content: dict[str, Any]) -> str:
        remote = self.tool.read(self.tool.file_id)
        node_id = self.tool.stable_id(artifact_id)
        expected = {"artifact_id": artifact_id, "kind": kind,
                    "namespace": self.tool.namespace, "content": content}
        mutation_id = f"synthetic-mutation:{digest(expected)}"
        if remote["nodes"].get(node_id) == expected:
            self.recovery_log.append({"artifact_id": artifact_id, "action": "reuse_observed_node"})
            return node_id
        try:
            result = self.tool.upsert(self.tool.file_id, artifact_id, kind, content,
                                      remote["read_receipt"], mutation_id)
        except WriteResponseTimeout:
            self.recovery_log.append({"artifact_id": artifact_id, "action": "timeout_readback_required"})
            observed = self.tool.read(self.tool.file_id)
            if observed["nodes"].get(node_id) != expected:
                raise ToolBlocked("write result unconfirmed; no blind retry")
            self.recovery_log.append({"artifact_id": artifact_id, "action": "confirmed_committed_write"})
            return node_id
        observed = self.tool.read(self.tool.file_id)
        if observed["nodes"].get(result) != expected:
            raise ToolBlocked("write readback mismatch")
        return result

    def sync(self, screens: dict[str, dict[str, Any]],
             flows: dict[str, dict[str, str]]) -> dict[str, str]:
        # Fail before any write when a required capability cannot be provided.
        self.tool.read(self.tool.file_id)
        self.tool._check("write", self.tool.file_id)
        if flows and "interaction" not in self.tool.capabilities:
            raise ToolBlocked("required interactions are unavailable")
        if any(flow.get("source") not in screens or flow.get("target") not in screens
               for flow in flows.values()):
            raise ToolBlocked("flow references an unknown required screen")
        result = {key: self._sync(key, "screen", value) for key, value in screens.items()}
        for key, value in flows.items():
            content = dict(value, source=result[value["source"]], target=result[value["target"]])
            result[key] = self._sync(key, "flow", content)
        return result
