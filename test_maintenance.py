import datetime as dt
import unittest
from maintenance import catalog_errors, workflow_status


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.now = dt.datetime(2026, 9, 5, tzinfo=dt.timezone.utc)
        self.run = {"head_sha": "current", "event": "push", "run_number": 1, "run_attempt": 1,
                    "status": "completed", "conclusion": "success", "updated_at": self.now.isoformat()}

    def status(self, runs):
        return workflow_status(runs, "current", self.now, 9)[0]

    def test_green_on_another_commit_is_not_evidence(self):
        self.assertEqual(self.status([{**self.run, "head_sha": "older"}]), "missing")

    def test_failed_retry_cannot_hide_behind_an_old_pass(self):
        self.assertEqual(self.status([self.run, {**self.run, "run_attempt": 2, "conclusion": "failure"}]), "failed")

    def test_pending_run_is_not_a_pass(self):
        self.assertEqual(self.status([{**self.run, "status": "in_progress"}]), "pending")

    def test_scheduled_evidence_expires(self):
        self.assertEqual(self.status([{**self.run, "updated_at": "2026-08-01T00:00:00Z"}]), "stale")

    def test_new_failure_supersedes_previous_success(self):
        self.assertEqual(self.status([self.run, {**self.run, "run_number": 2, "conclusion": "cancelled"}]), "failed")

    def test_current_success_is_accepted(self):
        self.assertEqual(self.status([self.run]), "passed")

    def test_new_tool_cannot_silently_escape_maintenance(self):
        projects = [{"id": "grindset", "tool": True}]
        self.assertTrue(catalog_errors({"tools": [{"id": "grindset"}, {"id": "new-tool"}]}, projects))
        self.assertTrue(catalog_errors({"tools": [{"id": "grindset"}] * 2}, projects))
        self.assertEqual(catalog_errors({"tools": [{"id": "grindset"}]}, projects), [])
