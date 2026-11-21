"""GEOLOGIA REST API: projects, plans, and transparent engine catalog."""
import argparse
from typing import Literal

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from geologia import __version__
from geologia import store
from geologia.planner import build_plan
from geologia.registry import get_engine, list_engines

app = FastAPI(
    title="GEOLOGIA API",
    version=__version__,
    description="Bilingual geoscience workspace. Phase 1 stores projects and analysis plans.",
)


class ProjectInput(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    description: str = Field("", max_length=2000)
    language: Literal["ar", "en"] = "ar"


class JobInput(BaseModel):
    request: str = Field(..., min_length=3, max_length=2000)
    language: Literal["ar", "en"] = "ar"


@app.on_event("startup")
def startup() -> None:
    store.initialize()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "geologia", "version": __version__,
            "engines_integrated": 0, "execution_enabled": False}


@app.get("/api/v1/engines")
def engines(domain: str | None = None) -> dict:
    items = list_engines(domain)
    return {"count": len(items), "engines": items}


@app.get("/api/v1/engines/{engine_id}")
def engine_detail(engine_id: str) -> dict:
    card = get_engine(engine_id)
    if card is None:
        raise HTTPException(status_code=404, detail="engine not found")
    return card


@app.get("/api/v1/projects")
def projects_list() -> dict:
    items = store.list_projects()
    return {"count": len(items), "projects": items}


@app.post("/api/v1/projects", status_code=201)
def projects_create(body: ProjectInput) -> dict:
    return store.create_project(body.name.strip(), body.description.strip(), body.language)


@app.get("/api/v1/projects/{project_id}")
def projects_get(project_id: str) -> dict:
    item = store.get_project(project_id)
    if item is None:
        raise HTTPException(status_code=404, detail="project not found")
    return item


@app.post("/api/v1/projects/{project_id}/jobs", status_code=201)
def jobs_create(project_id: str, body: JobInput) -> dict:
    if store.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    plan = build_plan(body.request, body.language)
    return store.create_job(project_id, body.request, body.language, plan)


@app.get("/api/v1/projects/{project_id}/jobs")
def jobs_list(project_id: str) -> dict:
    if store.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    items = store.list_jobs(project_id)
    return {"count": len(items), "jobs": items}


@app.get("/api/v1/jobs/{job_id}")
def jobs_get(job_id: str) -> dict:
    item = store.get_job(job_id)
    if item is None:
        raise HTTPException(status_code=404, detail="job not found")
    return item


def run() -> None:
    parser = argparse.ArgumentParser(description="Run GEOLOGIA API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run("geologia.api:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    run()
