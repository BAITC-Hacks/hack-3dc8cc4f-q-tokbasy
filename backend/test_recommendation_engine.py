"""Dataset-backed assertions for the recommendation engine."""

import unittest

from data_loader import CareerQuestData
from recommendation_engine import RecommendationEngine


class RecommendationEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = CareerQuestData()
        cls.engine = RecommendationEngine(cls.data)

    def test_real_profiles_are_consistent_and_ranked(self):
        for employee_id in ("E0001", "E0002", "E0004", "E0012"):
            gap = self.engine.career_gap(employee_id)
            recommendations = self.engine.recommendations(employee_id)
            self.assertGreaterEqual(gap["career_readiness"], 0)
            self.assertLessEqual(gap["career_readiness"], 100)
            self.assertEqual(
                [item["score"] for item in recommendations],
                sorted((item["score"] for item in recommendations), reverse=True),
            )
            for recommendation in recommendations:
                event = self.data.events_by_id[recommendation["event_id"]]
                effects = {effect["skill_id"]: effect for effect in event["develops_skills"]}
                for impact in recommendation["skill_impacts"]:
                    self.assertIn(impact["skill_id"], self.data.skills_by_id)
                    effect = effects[impact["skill_id"]]
                    self.assertEqual(impact["event_gain"], effect["gain"])
                    self.assertEqual(
                        impact["possible_new_level"],
                        min(impact["current_level"] + effect["gain"], effect["max_level"]),
                    )
                    self.assertEqual(
                        impact["actual_gain"], impact["possible_new_level"] - impact["current_level"]
                    )

    def test_history_and_explanations_are_factual(self):
        recommendations = self.engine.recommendations("E0002")
        self.assertTrue(any(item["history_signal"]["records_considered"] for item in recommendations))
        for item in recommendations:
            self.assertAlmostEqual(sum(item["score_components"].values()), item["score"], delta=0.4)
            factors = {reason["factor"] for reason in item["reasons"]}
            self.assertEqual(factors, {"grade_requirement", "skill_gap", "skill_gain", "history"})

    def test_engine_is_not_a_lowest_skill_rule(self):
        examples = []
        for employee in self.data.employees:
            recommendations = self.engine.recommendations(employee["employee_id"])
            if not recommendations:
                continue
            lowest = min(employee["skills"].values(), default=0)
            top_levels = [impact["current_level"] for impact in recommendations[0]["skill_impacts"]]
            if min(top_levels) > lowest:
                examples.append(employee["employee_id"])
        self.assertTrue(examples, "Expected a real profile whose top quest does not target its lowest skill")


if __name__ == "__main__":
    unittest.main()
