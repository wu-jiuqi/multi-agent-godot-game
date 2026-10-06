from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from pipeline_common import canonical_digest
from validate_penpot_browser_bridge import validate_penpot_browser_bridge


REF = "0" * 64


def ref(name: str) -> dict[str, object]:
    return {"artifact_id": f"evidence:{name}", "uri": f"repo://evidence/{name}.yaml", "sha256": REF}


def complete_task() -> dict[str, object]:
    request = {
        "request_id": "penpot-request:demo:01J7YQ2R8W3K6M4N9P0Q1R2S3T",
        "created_at": "2026-10-06T07:00:00Z",
        "source": "local_project",
        "operation": "cloud_browser_open",
        "action": "inspect",
        "target": {"url": "https://design.penpot.app/#/view/file?page-id=page", "file_id": "file", "page_id": "page", "shape_id": None},
        "input_refs": [ref("input")],
        "constraints": {"read_only": True, "requested_capabilities": ["read:penpot", "capture:penpot"], "timeout_seconds": 120},
        "local_note": "Inspect the current Penpot page before writing.",
    }
    ack = {
        "ack_id": "penpot-ack:demo:01J7YQ2R8W3K6M4N9P0Q1R2S3U",
        "status": "accepted",
        "at": "2026-10-06T07:00:05Z",
        "receiver": "dot_cloud_browser",
        "request_digest": canonical_digest(request),
        "connection_evidence": {
            "status": "verified",
            "observed_at": "2026-10-06T07:00:04Z",
            "browser": "cloud_browser",
            "browser_session_id": "session-demo",
            "tab_id": "tab-demo",
            "origin": "https://design.penpot.app",
            "evidence_ref": ref("connection"),
        },
        "note": "Connection observed; no browser token persisted.",
    }
    result = {
        "result_id": "penpot-result:demo:01J7YQ2R8W3K6M4N9P0Q1R2S3V",
        "status": "succeeded",
        "completed_at": "2026-10-06T07:00:08Z",
        "request_digest": canonical_digest(request),
        "ack_digest": canonical_digest(ack),
        "output": {
            "state": "Penpot page was inspected and IDs were captured.",
            "evidence_refs": [ref("operation")],
            "penpot_refs": {"file_id": "file", "page_id": "page", "shape_ids": []},
            "returned_at": "2026-10-06T07:00:08Z",
        },
    }
    task = {
        "schema_version": "game-production-penpot-browser-task/v1",
        "identity": {"task_id": "penpot-task:demo:01J7YQ2R8W3K6M4N9P0Q1R2S3W", "project_id": "demo", "revision": 1, "lifecycle_state": "completed"},
        "request": request,
        "ack": ack,
        "result": result,
        "integrity": {
            "canonicalization": "penpot-browser-task-canonical-json-v1",
            "digest_algorithm": "sha256",
            "request_digest": canonical_digest(request),
            "ack_digest": canonical_digest(ack),
            "result_digest": canonical_digest(result),
        },
    }
    return {"penpot_browser_task": task}


class PenpotBrowserBridgeTests(unittest.TestCase):
    def test_complete_request_ack_result_is_valid(self) -> None:
        result = validate_penpot_browser_bridge(complete_task())
        self.assertEqual("valid", result["state"], result)
        self.assertEqual([], result["errors"])

    def test_success_without_verified_connection_is_rejected(self) -> None:
        document = complete_task()
        connection = document["penpot_browser_task"]["ack"]["connection_evidence"]
        connection["status"] = "failed"
        connection["failure"] = {"code": "timeout", "detail": "No browser tab", "retryable": True, "route": "BRIDGE"}
        result = validate_penpot_browser_bridge(document)
        self.assertEqual("invalid", result["state"])

    def test_ack_request_digest_drift_is_reported(self) -> None:
        document = complete_task()
        document["penpot_browser_task"]["ack"]["request_digest"] = REF
        result = validate_penpot_browser_bridge(document)
        self.assertIn("ack.request_digest 不匹配 request", "\n".join(result["errors"]))

    def test_contract_and_docs_expose_bridge_boundary(self) -> None:
        template = (PLUGIN_ROOT / "contracts" / "penpot-browser-bridge.template.yaml").read_text(encoding="utf-8")
        docs = (PLUGIN_ROOT / "contracts" / "penpot-browser-bridge.md").read_text(encoding="utf-8")
        workflow = (PLUGIN_ROOT / "workflows" / "ui-production.md").read_text(encoding="utf-8")
        for marker in ("request:", "ack:", "result:", "cloud_browser_open", "connection_evidence", "BRIDGE", "直接控制浏览器"):
            with self.subTest(marker=marker):
                self.assertIn(marker, template + docs + workflow)


if __name__ == "__main__":
    unittest.main()
