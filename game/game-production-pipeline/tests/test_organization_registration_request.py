from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path

import yaml

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN_ROOT / "scripts" / "validate_organization_registration_request.py"
SAMPLE = PLUGIN_ROOT / "contracts" / "examples" / "organization-registration-request.yaml"
SPEC = importlib.util.spec_from_file_location("validate_organization_registration_request", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class OrganizationRegistrationRequestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = yaml.safe_load(SAMPLE.read_text(encoding="utf-8"))

    def test_pm_request_sample_is_valid(self) -> None:
        self.assertEqual([], MODULE.validate(self.document))

    def test_request_cannot_bypass_human_approval_or_apply(self) -> None:
        document = copy.deepcopy(self.document)
        root = document["organization_registration_request"]
        root["identity"]["status"] = "applied"
        root["approval"]["decision"] = "pending"
        self.assertTrue(any("approved" in error for error in MODULE.validate(document)))

    def test_request_must_route_to_agt_org(self) -> None:
        document = copy.deepcopy(self.document)
        document["organization_registration_request"]["routing"]["coordinator_agent_id"] = "AGT-PM"
        self.assertTrue(any("AGT-ORG" in error for error in MODULE.validate(document)))


if __name__ == "__main__":
    unittest.main()
