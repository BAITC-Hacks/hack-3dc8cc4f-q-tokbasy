"""Tests for dataset-backed HR dashboard aggregates."""

import unittest
from unittest.mock import patch

import main
from data_loader import CareerQuestData
from recommendation_engine import RecommendationEngine


class HRDashboardTests(unittest.TestCase):
    def setUp(self):
        self.data = CareerQuestData()
        self.engine = RecommendationEngine(self.data)
        self.patches = (
            patch.object(main, "data", self.data),
            patch.object(main, "engine", self.engine),
        )
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def test_dashboard_uses_valid_dataset_values(self):
        dashboard = main.get_hr_dashboard()
        self.assertEqual(dashboard["total_employees"], len(self.data.employees))
        self.assertLessEqual(len(dashboard["top_skill_gaps"]), 5)
        for gap in dashboard["top_skill_gaps"]:
            self.assertIn(gap["skill_id"], self.data.skills_by_id)
            self.assertEqual(gap["skill_name"], self.data.skills_by_id[gap["skill_id"]]["name"])
            self.assertGreater(gap["employee_count"], 0)
        self.assertGreaterEqual(dashboard["employees_without_recommendations"], 0)
        self.assertTrue(all(count >= 0 for count in dashboard["activity_status_counts"].values()))
        self.assertGreaterEqual(dashboard["participation_summary"]["completion_rate_percentage"], 0)
        self.assertLessEqual(dashboard["participation_summary"]["completion_rate_percentage"], 100)

    def test_runtime_completion_updates_participation_and_gaps(self):
        before = main.get_hr_dashboard()
        main.complete_quest("E0001", main.CompleteQuestRequest(event_id="EV_005"))
        after = main.get_hr_dashboard()
        self.assertEqual(
            after["participation_summary"]["total_activity_records"],
            before["participation_summary"]["total_activity_records"] + 1,
        )
        self.assertEqual(
            after["activity_status_counts"]["completed"],
            before["activity_status_counts"]["completed"] + 1,
        )
        self.assertEqual(
            after["participation_summary"]["completion_rate_percentage"],
            round(
                100 * after["participation_summary"]["completed_records"]
                / after["participation_summary"]["total_activity_records"],
                1,
            ),
        )


if __name__ == "__main__":
    unittest.main()
