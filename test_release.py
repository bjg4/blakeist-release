import copy
import unittest
from release import public_errors, validate_config


class ReleaseContractTests(unittest.TestCase):
    def setUp(self):
        self.manifest = {"standardVersion": 1, "channel": "firstdrop", "source": {"commit": "a" * 40, "dirty": False},
            "verification": {k: True for k in ("signature", "notarization", "gatekeeper", "roundTrip")},
            "acceptance": {"commit": "a" * 40, "testedBy": "Tester", "testedAt": "2026-09-05", "configurations": ["macOS 15 arm64"],
                "checks": {k: {"status": "passed", "evidence": "Recorded acceptance run"} for k in
                    ("cleanInstall", "coreWorkflow", "permissionRecovery", "terminationRecovery")}},
            "artifacts": [{"name": "app." + kind, "kind": kind, "sha256": "b" * 64, "bytes": 100,
                "url": "https://example.com/v1/app." + kind} for kind in ("dmg", "zip")]}
        self.manifest["acceptance"]["artifactHashes"] = {a["name"]: a["sha256"] for a in self.manifest["artifacts"]}

    def test_complete_firstdrop_qualifies(self):
        self.assertEqual(public_errors(self.manifest), [])

    def test_every_integrity_check_is_required(self):
        for check in self.manifest["verification"]:
            with self.subTest(check=check):
                candidate = copy.deepcopy(self.manifest)
                candidate["verification"][check] = False
                self.assertTrue(public_errors(candidate))

    def test_development_artifact_never_qualifies(self):
        self.manifest["channel"] = "private-alpha"
        self.assertTrue(public_errors(self.manifest))

    def test_acceptance_from_another_commit_rejected(self):
        self.manifest["acceptance"]["commit"] = "c" * 40
        self.assertTrue(public_errors(self.manifest))

    def test_dirty_source_rejected(self):
        self.manifest["source"]["dirty"] = True
        self.assertTrue(public_errors(self.manifest))

    def test_acceptance_of_different_binary_rejected(self):
        self.manifest["artifacts"][0]["sha256"] = "c" * 64
        self.assertTrue(public_errors(self.manifest))

    def test_both_install_formats_required(self):
        self.manifest["artifacts"].pop()
        self.assertTrue(public_errors(self.manifest))

    def test_stable_requires_upgrade_test(self):
        self.manifest["channel"] = "release"
        self.assertTrue(public_errors(self.manifest))
        self.manifest["acceptance"]["checks"]["upgrade"] = {"status": "passed", "evidence": "v1 to v2"}
        self.assertEqual(public_errors(self.manifest), [])

    def test_core_acceptance_cannot_be_waived(self):
        self.manifest["acceptance"]["checks"]["coreWorkflow"]["status"] = "not-applicable"
        self.assertTrue(public_errors(self.manifest))

    def test_unsigned_download_location_rejected(self):
        self.manifest["artifacts"][0]["url"] = "http://example.com/app.dmg"
        self.assertTrue(public_errors(self.manifest))

    def test_shell_string_is_not_a_build_command(self):
        config = {"id": "test", "name": "Test", "bundleId": "test.app", "appPath": "Test.app", "minimumSystemVersion": "13.0", "architectures": ["arm64"], "build": "make && upload"}
        with self.assertRaises(ValueError):
            validate_config(config)


if __name__ == "__main__":
    unittest.main()
