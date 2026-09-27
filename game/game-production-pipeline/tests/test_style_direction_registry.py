from __future__ import annotations

import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from pipeline_common import load_yaml  # noqa: E402
from validate_style_direction_registry import validate_style_direction_registry  # noqa: E402


REGISTRY = PLUGIN_ROOT / "skills" / "direct-game-art" / "style-directions" / "registry.yaml"


class StyleDirectionRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = load_yaml(REGISTRY)

    def test_current_registry_lists_verified_module(self) -> None:
        result = validate_style_direction_registry(self.document, plugin_root=PLUGIN_ROOT)
        self.assertEqual("valid", result["state"], result)
        self.assertEqual(["palette-knife-impasto"], [item["id"] for item in result["directions"]])
        self.assertEqual("matched", result["file_checks"][0]["state"])

    def test_duplicate_id_is_rejected(self) -> None:
        duplicate = copy.deepcopy(self.document)
        duplicate["style_direction_registry"]["directions"].append(
            copy.deepcopy(duplicate["style_direction_registry"]["directions"][0])
        )
        result = validate_style_direction_registry(duplicate, plugin_root=PLUGIN_ROOT)
        self.assertEqual("invalid", result["state"])
        self.assertIn("direction id 重复", "\n".join(result["errors"]))

    def test_stale_module_digest_is_rejected(self) -> None:
        stale = copy.deepcopy(self.document)
        stale["style_direction_registry"]["directions"][0]["digests"]["skill_sha256"] = "0" * 64
        result = validate_style_direction_registry(stale, plugin_root=PLUGIN_ROOT)
        self.assertEqual("invalid", result["state"])
        self.assertIn("skill_sha256 与 SKILL.md 不匹配", "\n".join(result["errors"]))

    def test_path_traversal_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.document)
        invalid["style_direction_registry"]["directions"][0]["path"] = "../outside"
        result = validate_style_direction_registry(invalid, plugin_root=PLUGIN_ROOT)
        self.assertEqual("invalid", result["state"])
        self.assertIn("必须是仓库内相对路径", "\n".join(result["errors"]))

    def test_cli_list_is_ascii_safe_and_read_only(self) -> None:
        before = REGISTRY.read_bytes()
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS / "validate_style_direction_registry.py"), str(REGISTRY), "--list"],
            cwd=PLUGIN_ROOT,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        completed.stdout.decode("ascii")
        payload = json.loads(completed.stdout)
        self.assertEqual("valid", payload["state"])
        self.assertEqual("palette-knife-impasto", payload["directions"][0]["id"])
        self.assertEqual(before, REGISTRY.read_bytes())


if __name__ == "__main__":
    unittest.main()
