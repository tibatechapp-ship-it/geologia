"""GEOLOGIA REST API: project workspace, safe dataset storage, and plan records."""
import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Literal
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field

from geologia import __version__
from geologia import store
from geologia.planner import build_plan
from geologia.registry import get_engine, list_engines

app = FastAPI(
    title="GEOLOGIA API",
    version=__version__,
    description="Bilingual geoscience workspace. Plans and stored datasets; no engine execution.",
)
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
ALLOWED_FORMATS = {".geojson", ".json", ".gpkg", ".tif", ".tiff", ".csv", ".las"}


class ProjectInput(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    description: str = Field("", max_length=2000)
    language: Literal["ar", "en"] = "ar"


class JobInput(BaseModel):
    request: str = Field(..., min_length=3, max_length=2000)
    language: Literal["ar", "en"] = "ar"


def _geojson_summary(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail="GeoJSON must be valid UTF-8 JSON") from exc
    kind = payload.get("type") if isinstance(payload, dict) else None
    if kind == "FeatureCollection":
        features = payload.get("features")
        if not isinstance(features, list):
            raise HTTPException(
                status_code=422, detail="FeatureCollection.features must be an array"
            )
        for feature in features:
            if not isinstance(feature, dict) or feature.get("type") != "Feature":
                raise HTTPException(status_code=422, detail="invalid GeoJSON Feature entry")
        return {"validation": "structural_only", "feature_count": len(features)}
    if kind == "Feature":
        return {"validation": "structural_only", "feature_count": 1}
    if kind in {"Point", "MultiPoint", "LineString", "MultiLineString",
                 "Polygon", "MultiPolygon", "GeometryCollection"}:
        return {"validation": "structural_only", "geometry_count": 1}
    raise HTTPException(status_code=422, detail="unsupported GeoJSON object type")


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


@app.post("/api/v1/projects/{project_id}/datasets", status_code=201)
async def dataset_upload(
    project_id: str,
    request: Request,
    dataset_name: str = Header(..., alias="X-Dataset-Name", min_length=2, max_length=120),
    filename: str = Header(..., alias="X-Filename", min_length=1, max_length=255),
    crs: str | None = Header(None, alias="X-CRS", max_length=100),
) -> dict:
    if store.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    safe_name = Path(filename.replace("\\", "/")).name
    suffix = Path(safe_name).suffix.lower()
    if suffix not in ALLOWED_FORMATS:
        raise HTTPException(status_code=415, detail="unsupported dataset format")
    declared = request.headers.get("content-length")
    if declared:
        try:
            if int(declared) > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="dataset exceeds upload limit")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid Content-Length") from exc

    storage = store.storage_path()
    temporary_path = None
    final_path = storage / f"{uuid4().hex}.blob"
    digest = hashlib.sha256()
    size = 0
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=storage, prefix=".upload-", delete=False
        ) as tmp:
            temporary_path = Path(tmp.name)
            async for chunk in request.stream():
                if not chunk:
                    continue
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="dataset exceeds upload limit")
                digest.update(chunk)
                tmp.write(chunk)
        if size == 0:
            raise HTTPException(status_code=422, detail="empty dataset")
        summary = {"validation": "stored_only"}
        effective_crs = crs.strip() if crs and crs.strip() else None
        if suffix in {".geojson", ".json"}:
            summary = _geojson_summary(temporary_path)
            effective_crs = effective_crs or "EPSG:4326"
        os.replace(temporary_path, final_path)
        clean_filename = safe_name.replace("\\", "/").split("/")[-1]
        try:
            item = store.create_dataset(
                project_id, name=dataset_name.strip(), file_format=suffix.lstrip("."),
                original_filename=clean_filename, content_path=str(final_path),
                sha256=digest.hexdigest(), size_bytes=size, crs=effective_crs, summary=summary,
            )
        except Exception:
            final_path.unlink(missing_ok=True)
            raise
        return item
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


@app.get("/api/v1/projects/{project_id}/datasets")
def datasets_list(project_id: str) -> dict:
    if store.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    items = store.list_datasets(project_id)
    return {"count": len(items), "datasets": items}


@app.get("/api/v1/datasets/{dataset_id}")
def datasets_get(dataset_id: str) -> dict:
    item = store.get_dataset(dataset_id)
    if item is None:
        raise HTTPException(status_code=404, detail="dataset not found")
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
