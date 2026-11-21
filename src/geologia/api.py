"""Phase 1 API: durable project and job metadata; execution is intentionally absent."""
import os
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from geologia import __version__
from geologia.ledger import Ledger, LedgerError

DB_PATH = os.environ.get("GEOLOGIA_DB", str(Path.cwd() / ".geologia" / "ledger.sqlite3"))
ledger = Ledger(DB_PATH)

app = FastAPI(title="GEOLOGIA", version=__version__,
              description="Durable project/job ledger. Jobs are recorded, not executed.")


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str = Field("", max_length=2000)


class JobCreate(BaseModel):
    kind: str = Field(..., min_length=1, max_length=80)
    payload: dict = Field(default_factory=dict)


class JobTransition(BaseModel):
    status: str
    result: dict | None = None
    error_code: str | None = Field(None, max_length=100)


def _error(exc: LedgerError):
    message = str(exc)
    if message.endswith("_not_found"):
        raise HTTPException(status_code=404, detail=message)
    if message == "idempotency_conflict":
        raise HTTPException(status_code=409, detail=message)
    if message.startswith("invalid_transition"):
        raise HTTPException(status_code=409, detail=message)
    raise HTTPException(status_code=422, detail=message)


@app.get("/health")
def health():
    return {"status": "ok", "service": "geologia", "version": __version__,
            "execution_enabled": False}


@app.post("/api/v1/projects", status_code=201)
def create_project(body: ProjectCreate):
    try:
        return ledger.create_project(body.name, body.description)
    except LedgerError as exc:
        _error(exc)


@app.get("/api/v1/projects")
def list_projects(limit: int = 50):
    return {"items": ledger.list_projects(limit)}


@app.get("/api/v1/projects/{project_id}")
def get_project(project_id: str):
    try:
        return ledger.get_project(project_id)
    except LedgerError as exc:
        _error(exc)


@app.post("/api/v1/projects/{project_id}/jobs", status_code=201)
def create_job(project_id: str, body: JobCreate,
               idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    try:
        return ledger.create_job(project_id, body.kind, body.payload, idempotency_key)
    except LedgerError as exc:
        _error(exc)


@app.get("/api/v1/jobs/{job_id}")
def get_job(job_id: str):
    try:
        return ledger.get_job(job_id)
    except LedgerError as exc:
        _error(exc)


@app.post("/api/v1/jobs/{job_id}/transition")
def transition_job(job_id: str, body: JobTransition):
    try:
        return ledger.transition_job(job_id, body.status, result=body.result,
                                    error_code=body.error_code)
    except LedgerError as exc:
        _error(exc)


@app.get("/api/v1/audit/{entity_id}")
def audit(entity_id: str, limit: int = 100):
    return {"items": ledger.events(entity_id, limit)}
