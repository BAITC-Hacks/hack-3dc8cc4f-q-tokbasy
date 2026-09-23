"""Load and join the Career Quest dataset."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parent.parent / "career_quest_dataset"


class CareerQuestData:
    """In-memory, read-only view of the hackathon dataset."""

    def __init__(self, data_dir: Path = DATA_DIR) -> None:
        self.data_dir = data_dir
        employees_document = self._read_json("employees.json")
        skills_document = self._read_json("skills.json")
        events_document = self._read_json("events.json")

        self.employees: list[dict[str, Any]] = employees_document["employees"]
        self.skills: list[dict[str, Any]] = skills_document["skills"]
        self.events: list[dict[str, Any]] = events_document["events"]
        self.activities = self._read_activities()

        self.employees_by_id = {item["employee_id"]: item for item in self.employees}
        self.skills_by_id = {item["skill_id"]: item for item in self.skills}
        self.events_by_id = {item["event_id"]: item for item in self.events}

    def _read_json(self, filename: str) -> dict[str, Any]:
        with (self.data_dir / filename).open(encoding="utf-8") as source:
            return json.load(source)

    def _read_activities(self) -> list[dict[str, Any]]:
        with (self.data_dir / "activity_history.csv").open(
            encoding="utf-8-sig", newline=""
        ) as source:
            return list(csv.DictReader(source))

    def employee_list(self) -> list[dict[str, Any]]:
        fields = ("employee_id", "full_name", "department", "role", "grade")
        return [{field: employee[field] for field in fields} for employee in self.employees]

    def employee_profile(self, employee_id: str) -> dict[str, Any] | None:
        employee = self.employees_by_id.get(employee_id)
        if employee is None:
            return None

        fields = (
            "employee_id",
            "full_name",
            "department",
            "role",
            "grade",
            "tenure_months",
            "work_format",
            "preferred_language",
            "career_goal",
        )
        profile = {field: employee[field] for field in fields}
        profile["skills"] = [
            {
                "skill_id": skill_id,
                "name": self.skills_by_id.get(skill_id, {}).get("name", skill_id),
                "level": level,
            }
            for skill_id, level in employee["skills"].items()
        ]

        history = []
        for activity in self.activities:
            if activity["employee_id"] != employee_id:
                continue
            event = self.events_by_id.get(activity["event_id"], {})
            history.append(
                {
                    "record_id": activity["record_id"],
                    "event_id": activity["event_id"],
                    "event_title": event.get("title", activity["event_id"]),
                    "date": activity["date"],
                    "status": activity["status"],
                    "completion_pct": int(activity["completion_pct"]),
                }
            )
        profile["recent_activity"] = sorted(
            history, key=lambda item: item["date"], reverse=True
        )[:8]
        return profile
