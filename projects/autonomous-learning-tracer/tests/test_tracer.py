"""Unit tests for the autonomous learning tracer project."""

import os
import sys
import unittest

tracer_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if tracer_src not in sys.path:
    sys.path.insert(0, tracer_src)

from runner import run_tracer_cycle


class TestTracerProject(unittest.TestCase):
    def test_full_tracer_cycle(self):
        results = run_tracer_cycle()
        self.assertEqual(results["task1_verification"], "VERIFIED_FAILURE")
        self.assertEqual(results["reviewer_decision"], "AUTO_COMMIT")
        self.assertTrue(results["v2_committed"])
        self.assertEqual(results["v2_version_id"], "v2")
        self.assertEqual(results["task2_verification"], "VERIFIED_SUCCESS")
        self.assertTrue(results["rollback_success"])
        self.assertEqual(results["restored_version_id"], "v2")


if __name__ == "__main__":
    unittest.main()
