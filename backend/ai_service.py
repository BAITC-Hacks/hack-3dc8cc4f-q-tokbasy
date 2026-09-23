"""OpenAI explanation layer for verified Career Quest recommendations.

This module deliberately owns no ranking logic.  It accepts a small, already
verified fact bundle and either returns presentation copy or a deterministic
fallback with the same shape.
"""

from __future__ import annotations

import json
import os
from typing import Any


DEFAULT_MODEL = "gpt-4.1-mini"
LANGUAGES = {"en": "English", "ru": "Russian", "kk": "Kazakh"}
OUTPUT_KEYS = {
    "headline",
    "summary",
    "why_this_quest",
    "expected_impact",
    "career_connection",
    "history_insight",
}


def verified_facts(employee: dict[str, Any], gap: dict[str, Any], recommendation: dict[str, Any]) -> dict[str, Any]:
    """Return the complete and intentionally narrow allow-list sent to OpenAI."""
    goal = employee.get("career_goal")
    return {
        "employee": {
            "role": employee["role"],
            "current_grade": employee["grade"],
            "target_role": gap["target_role"],
            "target_grade": gap["target_grade"],
            "career_goal": goal,
            "preferred_language": employee.get("preferred_language", "en"),
        },
        "recommendation": {
            "event_id": recommendation["event_id"],
            "event_title": recommendation["title"],
            "deterministic_score": recommendation["score"],
            "skill_impacts": recommendation["skill_impacts"],
            "history_signal": recommendation["history_signal"],
            "deterministic_reasons": recommendation["reasons"],
        },
    }


def deterministic_explanation(facts: dict[str, Any]) -> dict[str, Any]:
    """Build dashboard copy from facts only; always available and side-effect free."""
    employee = facts["employee"]
    rec = facts["recommendation"]
    impacts = rec["skill_impacts"]
    primary = impacts[0]
    impact_text = "; ".join(
        f"{item['skill_name']}: {item['current_level']} → {item['possible_new_level']}, target {item['target_level']}"
        for item in impacts
    )
    history = rec["history_signal"]
    return {
        "source": "deterministic",
        "headline": f"Build {primary['skill_name']} skills for {employee['target_grade']}",
        "summary": f"{rec['event_title']} addresses verified skill gaps for your target role.",
        "why_this_quest": [reason["text"] for reason in rec["deterministic_reasons"][:3]],
        "expected_impact": impact_text,
        "career_connection": (
            f"This is a concrete step toward the {primary['skill_name']} requirement "
            f"for {employee['target_role']} {employee['target_grade']}."
        ),
        "history_insight": (
            f"Your participation history included {history['records_considered']} similar "
            f"record(s) and was included in the deterministic score."
        ),
    }


def _valid_output(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != OUTPUT_KEYS:
        return False
    scalar_keys = OUTPUT_KEYS - {"why_this_quest"}
    if any(not isinstance(value[key], str) or not value[key].strip() for key in scalar_keys):
        return False
    reasons = value["why_this_quest"]
    return isinstance(reasons, list) and 1 <= len(reasons) <= 3 and all(
        isinstance(item, str) and item.strip() for item in reasons
    )


class AICareerCoach:
    """Thin Responses API adapter with fail-closed output validation."""

    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: float = 3.0) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
        self.timeout = timeout

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def explain(self, facts: dict[str, Any]) -> dict[str, Any]:
        fallback = deterministic_explanation(facts)
        if not self.enabled:
            return fallback
        try:
            from openai import OpenAI

            language = LANGUAGES.get(facts["employee"].get("preferred_language"), "English")
            client = OpenAI(api_key=self.api_key, timeout=self.timeout, max_retries=0)
            response = client.responses.create(
                model=self.model,
                instructions=(
                    "You are an employee-facing career coach. Use only the supplied facts. "
                    "Do not invent employee information, event information, scores, requirements, "
                    "skill gains, or history. Never change identifiers or numbers. Write concise, "
                    f"supportive, professional dashboard copy in {language}; avoid exaggerated claims."
                ),
                input=json.dumps(facts, ensure_ascii=False, separators=(",", ":")),
                max_output_tokens=500,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "career_coach_explanation",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "headline": {"type": "string"},
                                "summary": {"type": "string"},
                                "why_this_quest": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 3},
                                "expected_impact": {"type": "string"},
                                "career_connection": {"type": "string"},
                                "history_insight": {"type": "string"},
                            },
                            "required": sorted(OUTPUT_KEYS),
                        },
                    }
                },
            )
            output = json.loads(response.output_text)
            if not _valid_output(output):
                return fallback
            return {"source": "openai", **output}
        except Exception:
            # Availability, quota, SDK, timeout, network, and malformed-output
            # failures are intentionally indistinguishable to API consumers.
            return fallback
