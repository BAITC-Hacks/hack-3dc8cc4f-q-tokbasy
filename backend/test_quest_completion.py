"""Runtime quest-completion tests against the supplied catalog."""

import hashlib
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

import main
from data_loader import CareerQuestData
from recommendation_engine import RecommendationEngine


DATA_FILES = ("employees.json", "events.json", "skills.json", "activity_history.csv")


class QuestCompletionTests(unittest.TestCase):
    def setUp(self):
        self.data = CareerQuestData()
        self.engine = RecommendationEngine(self.data)
        self.data_dir = Path(self.data.data_dir)
        self.file_hashes = {
            name: hashlib.sha256((self.data_dir / name).read_bytes()).hexdigest()
            for name in DATA_FILES
        }
        self.patches = (
            patch.object(main, "data", self.data),
            patch.object(main, "engine", self.engine),
        )
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def complete(self, employee_id="E0001", event_id="EV_005"):
        return main.complete_quest(employee_id, main.CompleteQuestRequest(event_id=event_id))

    def test_valid_completion_uses_real_effects_and_updates_all_runtime_views(self):
        employee = self.data.employees_by_id["E0001"]
        original_skills = employee["skills"].copy()
        before_gap = self.engine.career_gap("E0001")
        before_ids = [item["event_id"] for item in self.engine.recommendations("E0001")]

        result = self.complete()

        event = self.data.events_by_id["EV_005"]
        effects = {effect["skill_id"]: effect for effect in event["develops_skills"]}
        self.assertEqual(result["status"], "completed")
        self.assertEqual({item["skill_id"] for item in result["skill_changes"]}, set(effects))
        for change in result["skill_changes"]:
            effect = effects[change["skill_id"]]
            expected = min(change["before"] + effect["gain"], effect["max_level"], 5)
            self.assertEqual(change["after"], expected)
            self.assertEqual(change["actual_gain"], expected - change["before"])
            self.assertLessEqual(change["after"], effect["max_level"])
            self.assertLessEqual(change["after"], 5)

        changed = set(effects)
        for skill_id, level in original_skills.items():
            if skill_id not in changed:
                self.assertEqual(employee["skills"][skill_id], level)

        after_gap = self.engine.career_gap("E0001")
        self.assertEqual(result["career_readiness_before"], before_gap["career_readiness"])
        self.assertEqual(result["career_readiness_after"], after_gap["career_readiness"])
        self.assertGreater(after_gap["career_readiness"], before_gap["career_readiness"])
        self.assertNotIn("EV_005", [item["event_id"] for item in self.engine.recommendations("E0001")])
        self.assertIn("EV_005", before_ids)
        profile = self.data.employee_profile("E0001")
        self.assertEqual(profile["recent_activity"][0]["event_id"], "EV_005")
        self.assertEqual(profile["recent_activity"][0]["status"], "completed")

    def test_catalog_max_level_and_global_five_cap_are_respected(self):
        employee = self.data.employees_by_id["E0001"]
        # EV_005 has a System Design catalog cap of 3. Put the runtime level at
        # that cap to verify the completion calculation reports a zero gain.
        employee["skills"]["SK_SYSTEM_DESIGN"] = 3
        result = self.complete()
        system_design = next(x for x in result["skill_changes"] if x["skill_id"] == "SK_SYSTEM_DESIGN")
        self.assertEqual((system_design["before"], system_design["after"], system_design["actual_gain"]), (3, 3, 0))
        self.assertTrue(all(change["after"] <= 5 for change in result["skill_changes"]))

    def test_duplicate_non_recurring_completion_is_rejected(self):
        self.complete()
        with self.assertRaises(HTTPException) as caught:
            self.complete()
        self.assertEqual(caught.exception.status_code, 409)

    def test_invalid_employee_and_event_are_rejected(self):
        with self.assertRaises(HTTPException) as employee_error:
            self.complete(employee_id="NOT_REAL")
        self.assertEqual(employee_error.exception.status_code, 404)
        with self.assertRaises(HTTPException) as event_error:
            self.complete(event_id="NOT_REAL")
        self.assertEqual(event_error.exception.status_code, 404)

    def test_ineligible_event_is_rejected(self):
        with self.assertRaises(HTTPException) as caught:
            self.complete(event_id="EV_006")
        self.assertEqual(caught.exception.status_code, 422)

    def test_source_dataset_files_are_never_modified(self):
        self.complete()
        actual = {
            name: hashlib.sha256((self.data_dir / name).read_bytes()).hexdigest()
            for name in DATA_FILES
        }
        self.assertEqual(actual, self.file_hashes)


if __name__ == "__main__":
    unittest.main()
