"""Career Quest API."""

import asyncio

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from data_loader import CareerQuestData
from recommendation_engine import RecommendationEngine
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
