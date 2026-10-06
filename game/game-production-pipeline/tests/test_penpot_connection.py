from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from validate_penpot_connection import check_penpot_mcp_connection, main


class PenpotConnectionTests(unittest.TestCase):
    def test_connected_probe_returns_only_safe_connection_state(self) -> None:
        result = check_penpot_mcp_connection(
            lambda: {
                "connected": True,
                "endpoint": "https://user:password@design.penpot.app/mcp?token=secret#page",
                "server": "penpot-mcp",
                "transport": "streamable-http",
                "token": "must-not-leak",
            },
            checked_at=datetime(2026, 10, 6, 8, 0, tzinfo=timezone.utc),
        )
        self.assertEqual("connected", result["state"])
        self.assertEqual("https://design.penpot.app/mcp", result["connection"]["endpoint"])
        self.assertNotIn("token", json.dumps(result, ensure_ascii=False))
        self.assertIsNone(result["error"])

    def test_disconnected_probe_has_connection_error(self) -> None:
        result = check_penpot_mcp_connection(lambda: {"connected": False})
        self.assertEqual("disconnected", result["state"])
        self.assertEqual("NOT_CONNECTED", result["error"]["code"])
        self.assertFalse(result["connection"]["connected"])

    def test_probe_exception_is_error_without_exception_details(self) -> None:
        def probe() -> object:
            raise RuntimeError("authorization=super-secret")

        result = check_penpot_mcp_connection(probe)
        self.assertEqual("error", result["state"])
        self.assertEqual("PROBE_FAILED", result["error"]["code"])
        self.assertNotIn("super-secret", json.dumps(result, ensure_ascii=False))

    def test_malformed_probe_is_error(self) -> None:
        result = check_penpot_mcp_connection(lambda: {"status": "connected"})
        self.assertEqual("error", result["state"])
        self.assertEqual("PROBE_INVALID", result["error"]["code"])

    def test_malformed_endpoint_is_ignored_without_failing_status_check(self) -> None:
        result = check_penpot_mcp_connection(
            lambda: {"connected": True, "endpoint": "https://penpot.example:bad-port/mcp"}
        )
        self.assertEqual("connected", result["state"])
        self.assertNotIn("endpoint", result["connection"])

    def test_connected_with_error_is_inconsistent(self) -> None:
        result = check_penpot_mcp_connection(
            lambda: {"connected": True, "error": {"code": "AUTH", "message": "token=secret"}}
        )
        self.assertEqual("error", result["state"])
        self.assertEqual("AUTH", result["error"]["code"])
        self.assertNotIn("secret", json.dumps(result, ensure_ascii=False))

    def test_cli_accepts_json_and_returns_json_only(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = main(["--probe-json", '{"connected": false, "error": "offline"}'])
        result = json.loads(output.getvalue())
        self.assertEqual(2, exit_code)
        self.assertEqual("disconnected", result["state"])
        self.assertEqual("offline", result["error"]["message"])


if __name__ == "__main__":
    unittest.main()
