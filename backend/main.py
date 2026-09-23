"""Career Quest iteration-one API."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from data_loader import CareerQuestData


app = FastAPI(title="Career Quest API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

data = CareerQuestData()


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


@app.get("/api/events")
def list_events() -> list[dict]:
    return data.events


@app.get("/api/skills")
def list_skills() -> list[dict]:
    return data.skills
