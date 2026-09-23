"""Career Quest API."""

import asyncio
from threading import Lock

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from data_loader import CareerQuestData
from recommendation_engine import RECURRING_EVENT_IDS, RecommendationEngine
from ai_service import AICareerCoach, verified_facts


app = FastAPI(title="Career Quest API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

data = CareerQuestData()
engine = RecommendationEngine(data)
ai_coach = AICareerCoach()
completion_lock = Lock()


class CompleteQuestRequest(BaseModel):
    event_id: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/employees")
def list_employees() -> list[dict]:
    return data.employee_list()


@app.get("/api/employees/{employee_id}")
def get_employee(employee_id: str) -> dict:
    profile = data.employee_profile(employee_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    return profile


@app.get("/api/employees/{employee_id}/career-gap")
def get_career_gap(employee_id: str) -> dict:
    report = engine.career_gap(employee_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    return report


@app.get("/api/employees/{employee_id}/recommendations")
def get_recommendations(employee_id: str) -> list[dict]:
    recommendations = engine.recommendations(employee_id)
    if recommendations is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    return recommendations


@app.post("/api/employees/{employee_id}/complete-quest")
def complete_quest(employee_id: str, request: CompleteQuestRequest) -> dict:
    """Apply catalog-defined effects to the session's in-memory state."""
    with completion_lock:
        employee = data.employees_by_id.get(employee_id)
        if employee is None:
            raise HTTPException(status_code=404, detail="Employee not found")
        event = data.events_by_id.get(request.event_id)
        if event is None:
            raise HTTPException(status_code=404, detail="Event not found")

        already_completed = any(
            activity["employee_id"] == employee_id
            and activity["event_id"] == request.event_id
            and activity["status"] == "completed"
            for activity in data.activities
        )
        if already_completed and request.event_id not in RECURRING_EVENT_IDS:
            raise HTTPException(status_code=409, detail="Quest already completed")

        useful_events = {
            item["event_id"] for item in (engine.recommendations(employee_id, limit=len(data.events)) or [])
        }
        if request.event_id not in useful_events:
            raise HTTPException(
                status_code=422,
                detail="Event is not currently eligible and useful for this employee",
            )

        readiness_before = engine.career_gap(employee_id)["career_readiness"]
        skill_changes = []
        for effect in event["develops_skills"]:
            skill_id = effect["skill_id"]
            before = employee["skills"].get(skill_id, 0)
            after = min(before + effect["gain"], effect["max_level"], 5)
            employee["skills"][skill_id] = after
            skill_changes.append({
                "skill_id": skill_id,
                "skill_name": data.skills_by_id.get(skill_id, {}).get("name", skill_id),
                "before": before,
                "after": after,
                "actual_gain": after - before,
            })

        sequence = sum(record["record_id"].startswith("RUNTIME_") for record in data.activities) + 1
        data.activities.append({
            "record_id": f"RUNTIME_{sequence:04d}",
            "employee_id": employee_id,
            "event_id": request.event_id,
            "date": engine.snapshot_date.isoformat(),
            "status": "completed",
            "completion_pct": "100",
        })
        readiness_after = engine.career_gap(employee_id)["career_readiness"]
        return {
            "employee_id": employee_id,
            "event_id": request.event_id,
            "event_title": event["title"],
            "status": "completed",
            "skill_changes": skill_changes,
            "career_readiness_before": readiness_before,
            "career_readiness_after": readiness_after,
        }


@app.get("/api/employees/{employee_id}/ai-recommendations")
async def get_ai_recommendations(employee_id: str) -> dict:
    """Decorate immutable deterministic recommendations with coach copy."""
    employee = data.employees_by_id.get(employee_id)
    gap = engine.career_gap(employee_id)
    recommendations = engine.recommendations(employee_id, limit=3)
    if employee is None or gap is None or recommendations is None:
        raise HTTPException(status_code=404, detail="Employee not found")

    enriched = []
    for recommendation in recommendations:
        facts = verified_facts(employee, gap, recommendation)
        explanation = await asyncio.to_thread(ai_coach.explain, facts)
        # Merge only under a new field: model output can never overwrite facts.
        enriched.append({**recommendation, "explanation": explanation})
    return {
        "ai_enabled": ai_coach.enabled,
        "provider": "openai" if ai_coach.enabled else None,
        "model": ai_coach.model if ai_coach.enabled else None,
        "recommendations": enriched,
    }


@app.get("/api/events")
def list_events() -> list[dict]:
    return data.events


@app.get("/api/skills")
def list_skills() -> list[dict]:
    return data.skills
