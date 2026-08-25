"""Integration and Acceptance Tests for Autonomy Pilot 1."""

import os
import sys
import shutil
import tempfile
import unittest

pilot_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if pilot_src not in sys.path:
    sys.path.insert(0, pilot_src)

from runner import AutonomyPilotRunner


class TestAutonomyPilot(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.runner = AutonomyPilotRunner(base_storage_dir=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_full_pilot_execution_and_metrics(self):
        results = self.runner.run_full_pilot()
        metrics = results["metrics"]

        # Invariant 1: 10 normal tasks executed across 3 fresh sessions
        self.assertEqual(metrics["tasks_total"], 10)
        self.assertEqual(results["sessions_count"], 3)

        # Invariant 2: 0 manual developer interventions
        self.assertEqual(metrics["manual_developer_interventions"], 0)

        # Invariant 3: 100% lifecycle completeness
        self.assertEqual(metrics["lifecycle_complete_count"], 10)

        # Invariant 4: All normal tasks verified successfully
        self.assertEqual(metrics["verified_successes"], 10)
        self.assertEqual(metrics["verified_failures"], 0)

        # Invariant 5: 0 repeated failures
        self.assertEqual(metrics["repeated_failures"], 0)

        # Invariant 6: Reuses observed
        self.assertEqual(metrics["memory_reuses"], 2)
        self.assertEqual(metrics["learned_skill_reuses"], 1)
        self.assertEqual(metrics["episodic_retrieval_uses"], 1)

        # Invariant 7: User intervention rate (1 correction in 10 tasks)
        self.assertAlmostEqual(metrics["user_intervention_rate"], 0.1)

        # Invariant 8: Controlled safety test succeeded separately
        safety = results["controlled_safety_test"]
        self.assertTrue(safety["curator_triggered"])
        self.assertTrue(safety["applied"])
        self.assertTrue(safety["rollback_verified"])

    def test_declarative_memory_lifecycle(self):
        results = self.runner.run_full_pilot()
        logs = {log["task_id"]: log for log in results["task_logs"]}

        # Task 1 naturally ingested memory
        self.assertTrue(len(logs["pilot_task_01"]["learned_memories"]) > 0)

        # Task 5 in fresh session reused memory
        self.assertTrue(logs["pilot_task_05"]["memory_reused"])

        # Task 7 ingested correction
        self.assertTrue(logs["pilot_task_07"]["user_correction"])

        # Task 8 in fresh session reused corrected truth
        self.assertTrue(logs["pilot_task_08"]["memory_reused"])

    def test_procedural_improvement_lifecycle(self):
        results = self.runner.run_full_pilot()
        logs = {log["task_id"]: log for log in results["task_logs"]}

        # Task 3 required recovery and produced v2
        self.assertTrue(logs["pilot_task_03"]["recovery_required"])
        self.assertTrue(logs["pilot_task_03"]["learning_mutation_created"])

        # Task 6 in fresh session achieved direct success using v2 (0 recoveries)
        self.assertTrue(logs["pilot_task_06"]["learned_skill_reused"])
        self.assertFalse(logs["pilot_task_06"]["recovery_required"])
        self.assertEqual(logs["pilot_task_06"]["verification"], "VERIFIED_SUCCESS")


if __name__ == "__main__":
    unittest.main()
