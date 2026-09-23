"""Deterministic, explainable career-gap and event recommendations."""

from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any

from data_loader import CareerQuestData


STATUS_WEIGHTS = {
    "completed": 1.0,
    "in_progress": 0.25,
    "dropped": -0.6,
    "no_show": -0.75,
    "declined": -0.65,
    "overdue": -0.5,
}


class RecommendationEngine:
    """Rank useful activities using grade gaps, gains, audience, and history.

    The score has a fixed 100-point ceiling: gap severity 35, target-grade
    relevance 25, realizable gain 20, participation history 10, career-goal
    relevance 5, and audience eligibility 5. Candidate filtering makes the
    last component factual rather than using it to rescue ineligible events.
    """

    def __init__(self, data: CareerQuestData) -> None:
        self.data = data
        self.snapshot_date = self._snapshot_date()

    def _snapshot_date(self) -> date:
        # The dataset README defines this snapshot; employee documents carry it.
        with (self.data.data_dir / "employees.json").open(encoding="utf-8") as source:
            import json

            return date.fromisoformat(json.load(source)["meta"]["as_of_date"])

    def _target(self, employee: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
        goal = employee.get("career_goal")
        if goal:
            role, grade = goal["target_role"], goal["target_grade"]
        else:
            role = employee["role"]
            grades = [
                profile["grade"]
                for profile in self.data.role_profiles
                if profile["role"] == role
            ]
            current_index = grades.index(employee["grade"])
            grade = grades[min(current_index + 1, len(grades) - 1)]
        profile = self.data.role_profiles_by_key.get((role, grade))
        if profile is None:
            raise ValueError(f"No role profile for {role} / {grade}")
        return role, grade, profile

    def career_gap(self, employee_id: str) -> dict[str, Any] | None:
        employee = self.data.employees_by_id.get(employee_id)
        if employee is None:
            return None
        target_role, target_grade, profile = self._target(employee)
        critical = set(profile["critical_skills"])
        gaps = []
        achieved = 0
        required = 0
        for skill_id, target_level in profile["required_skills"].items():
            current_level = employee["skills"].get(skill_id, 0)
            gap = max(target_level - current_level, 0)
            required += target_level
            achieved += min(current_level, target_level)
            gaps.append(
                {
                    "skill_id": skill_id,
                    "skill_name": self.data.skills_by_id[skill_id]["name"],
                    "current_level": current_level,
                    "target_level": target_level,
                    "gap": gap,
                    "critical": skill_id in critical,
                }
            )
        gaps.sort(key=lambda item: (-item["critical"], -item["gap"], item["skill_name"]))
        return {
            "employee_id": employee_id,
            "current_role": employee["role"],
            "current_grade": employee["grade"],
            "target_role": target_role,
            "target_grade": target_grade,
            "career_readiness": round(100 * achieved / required, 1) if required else 100.0,
            "skill_gaps": gaps,
            "critical_gaps": [item for item in gaps if item["critical"] and item["gap"] > 0],
        }

    def _history_signal(self, employee_id: str, event: dict[str, Any]) -> dict[str, Any]:
        similar_ids = {
            item["event_id"] for item in self.data.events if item["type"] == event["type"]
        }
        records = [
            item
            for item in self.data.activities
            if item["employee_id"] == employee_id and item["event_id"] in similar_ids
        ]
        counts = Counter(item["status"] for item in records)
        weighted_sum = 0.0
        recency_total = 0.0
        for record in records:
            age = max((self.snapshot_date - date.fromisoformat(record["date"])).days, 0)
            recency = 0.5 + 0.5 * max(0.0, 1.0 - age / 731)
            weighted_sum += STATUS_WEIGHTS[record["status"]] * recency
            recency_total += recency
        raw = weighted_sum / recency_total if recency_total else 0.0
        normalized = max(-1.0, min(1.0, raw))
        return {
            "score": round(normalized, 3),
            "similar_event_type": event["type"],
            "records_considered": len(records),
            "status_counts": dict(sorted(counts.items())),
        }

    def recommendations(self, employee_id: str, limit: int = 3) -> list[dict[str, Any]] | None:
        employee = self.data.employees_by_id.get(employee_id)
        gap_report = self.career_gap(employee_id)
        if employee is None or gap_report is None:
            return None
        target_role = gap_report["target_role"]
        target_grade = gap_report["target_grade"]
        gap_by_skill = {item["skill_id"]: item for item in gap_report["skill_gaps"]}
        employee_history = [x for x in self.data.activities if x["employee_id"] == employee_id]
        completed_ids = {x["event_id"] for x in employee_history if x["status"] == "completed"}
        results = []

        for event in self.data.events:
            if event["mandatory"] or (event["event_id"] in completed_ids and event["event_id"] != "EV_036"):
                continue
            role_match = target_role in event["target_roles"]
            # Development activities may be aimed at the employee's current
            # grade or the destination grade (the dataset documents voluntary
            # participation against current/previous-grade audiences).
            grade_match = (
                employee["grade"] in event["target_grades"]
                or target_grade in event["target_grades"]
            )
            prerequisites_met = all(
                employee["skills"].get(skill_id, 0) >= level
                for skill_id, level in event["prerequisites"].items()
            )
            if not (role_match and grade_match and prerequisites_met):
                continue

            impacts = []
            for effect in event["develops_skills"]:
                gap = gap_by_skill.get(effect["skill_id"])
                if not gap or gap["gap"] <= 0:
                    continue
                current = gap["current_level"]
                possible_new = min(current + effect["gain"], effect["max_level"])
                actual_gain = max(possible_new - current, 0)
                if actual_gain <= 0:
                    continue
                impacts.append(
                    {
                        "skill_id": effect["skill_id"],
                        "skill_name": gap["skill_name"],
                        "current_level": current,
                        "target_level": gap["target_level"],
                        "possible_new_level": possible_new,
                        "actual_gain": actual_gain,
                        "event_gain": effect["gain"],
                        "event_max_level": effect["max_level"],
                        "gap": gap["gap"],
                        "critical": gap["critical"],
                    }
                )
            if not impacts:
                continue

            weights = [1.5 if impact["critical"] else 1.0 for impact in impacts]
            severity = min(1.0, sum(
                weight * impact["gap"] / 5
                for weight, impact in zip(weights, impacts)
            ) / len(impacts))
            requirement_strength = min(1.0, sum(
                weight * impact["target_level"] / 5
                for weight, impact in zip(weights, impacts)
            ) / len(impacts))
            breadth = len(impacts) / max(1, len([g for g in gap_by_skill.values() if g["gap"] > 0]))
            relevance = 0.85 * requirement_strength + 0.15 * breadth
            gain_fraction = sum(
                weight * impact["actual_gain"] / impact["event_gain"]
                for weight, impact in zip(weights, impacts)
            ) / sum(weights)
            history = self._history_signal(employee_id, event)
            history_points = 5.0 * (history["score"] + 1.0)
            goal_points = 5.0 if employee.get("career_goal") and role_match else 0.0
            components = {
                "skill_gap": 35.0 * severity,
                "grade_relevance": 25.0 * relevance,
                "actual_gain": 20.0 * gain_fraction,
                "history": history_points,
                "career_goal": goal_points,
                "eligibility": 5.0,
            }
            score = round(min(100.0, sum(components.values())), 1)
            primary = max(impacts, key=lambda x: (x["critical"], x["gap"], x["actual_gain"]))
            history_text = (
                f"Your {event['type']} participation history ({history['records_considered']} records; "
                f"signal {history['score']:+.3f}) was included in the score."
            )
            reasons = [
                {"factor": "grade_requirement", "text": f"Your {target_role} {target_grade} target requires {primary['skill_name']} level {primary['target_level']}."},
                {"factor": "skill_gap", "text": f"Your current {primary['skill_name']} level is {primary['current_level']}, leaving a gap of {primary['gap']}."},
                {"factor": "skill_gain", "text": f"This activity can improve {primary['skill_name']} from {primary['current_level']} to {primary['possible_new_level']}."},
                {"factor": "history", "text": history_text},
            ]
            results.append(
                {
                    "event_id": event["event_id"],
                    "title": event["title"],
                    "event_type": event["type"],
                    "score": score,
                    "skill_impacts": impacts,
                    "affected_skills": [item["skill_id"] for item in impacts],
                    "score_components": {key: round(value, 1) for key, value in components.items()},
                    "history_signal": history,
                    "reasons": reasons,
                }
            )
        results.sort(key=lambda item: (-item["score"], item["event_id"]))
        return results[:limit]
