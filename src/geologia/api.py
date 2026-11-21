"""GEOLOGIA REST API: project workspace, safe dataset storage, and plan records."""
import argparse
import math
import hashlib
import json
import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from geologia import __version__
from geologia import store
from geologia.planner import build_plan
from geologia.registry import get_engine, list_engines
from geologia.vector import inspect_csv, inspect_geojson

@asynccontextmanager
async def lifespan(_: FastAPI):
    store.initialize()
    yield


app = FastAPI(
    title="GEOLOGIA API",
    version=__version__,
    description="Bilingual geoscience workspace. Plans and stored datasets; no engine execution.",
    lifespan=lifespan,
)
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
ALLOWED_FORMATS = {".geojson", ".json", ".gpkg", ".tif", ".tiff", ".csv", ".las"}
ALLOWED_DATA_ROLES = {
    "dem", "geology_map", "recharge_estimate", "water_levels_timeseries", "well_logs",
    "structural_orientations", "contacts", "waveforms_or_catalog", "station_metadata",
    "geochemistry_samples", "geophysics_surveys", "aoi_boundary", "data_layers",
    "crs_definition", "imagery", "ground_control_points",
}


class ProjectInput(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    description: str = Field("", max_length=2000)
    language: Literal["ar", "en"] = "ar"

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("project name must contain at least two non-space characters")
        return value

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str) -> str:
        return value.strip()


class JobInput(BaseModel):
    request: str = Field(..., min_length=3, max_length=2000)
    language: Literal["ar", "en"] = "ar"

    @field_validator("request")
    @classmethod
    def normalize_request(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("request must contain at least three non-space characters")
        return value


class ReprojectInput(BaseModel):
    target_crs: str = Field(..., min_length=1, max_length=200)


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON numeric constant: {value}")


def _finite_json_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("JSON numeric value must be finite")
    return parsed


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _read_json(path: Path) -> dict:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=_reject_json_constant,
            parse_float=_finite_json_float,
            object_pairs_hook=_unique_json_object,
        )
    except RecursionError as exc:
        raise ValueError("JSON nesting exceeds the supported depth") from exc


def _geojson_summary(path: Path) -> dict:
    try:
        payload = _read_json(path)
    except (UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(
            status_code=422, detail="GeoJSON must be valid UTF-8 JSON with finite numbers"
        ) from exc
    try:
        metrics = inspect_geojson(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"invalid GeoJSON: {exc}") from exc
    return {"validation": "structural_only", "feature_count": metrics["feature_count"],
            "coordinate_count": metrics["coordinate_count"], "bbox_xy": metrics["bbox_xy"]}


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
    data_role: str | None = Header(None, alias="X-Data-Role", max_length=80),
) -> dict:
    if store.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    dataset_name = dataset_name.strip()
    if len(dataset_name) < 2:
        raise HTTPException(
            status_code=422,
            detail="dataset name must contain at least two non-space characters",
        )
    if data_role and data_role not in ALLOWED_DATA_ROLES:
        raise HTTPException(status_code=422, detail="unknown dataset data role")
    safe_name = Path(filename.replace("\\", "/")).name
    suffix = Path(safe_name).suffix.lower()
    if suffix not in ALLOWED_FORMATS:
        raise HTTPException(status_code=415, detail="unsupported dataset format")
    declared = request.headers.get("content-length")
    if declared:
        try:
            declared_size = int(declared)
            if declared_size < 0:
                raise ValueError("negative Content-Length")
            if declared_size > MAX_UPLOAD_BYTES:
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
            if effective_crs:
                from geologia.geospatial import validate_geojson_crs

                try:
                    crs_report = validate_geojson_crs(_read_json(temporary_path), effective_crs)
                except RuntimeError as exc:
                    raise HTTPException(status_code=503, detail=str(exc)) from exc
                except ValueError as exc:
                    raise HTTPException(status_code=422, detail=str(exc)) from exc
                effective_crs = crs_report["canonical"]
                summary["crs_validation"] = crs_report
            else:
                effective_crs = "EPSG:4326"
                bbox = summary["bbox_xy"]
                if bbox and (bbox[0] < -180 or bbox[2] > 180
                             or bbox[1] < -90 or bbox[3] > 90):
                    raise HTTPException(
                        status_code=422,
                        detail=(
                            "default GeoJSON CRS is WGS84; coordinates exceed "
                            "longitude/latitude bounds"
                        ),
                    )
                summary["crs_validation"] = {
                    "canonical": effective_crs,
                    "coordinate_bounds_check": "passed",
                    "crs_inference_performed": False,
                    "scientific_validation": False,
                }
        elif suffix == ".csv":
            try:
                summary = inspect_csv(temporary_path)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            summary["validation"] = "csv_structural_only"
            if summary["ragged_row_count"]:
                summary["warnings"] = ["rows_have_inconsistent_column_counts"]
        os.replace(temporary_path, final_path)
        clean_filename = safe_name.replace("\\", "/").split("/")[-1]
        try:
            item = store.create_dataset(
                project_id, name=dataset_name, file_format=suffix.lstrip("."),
                original_filename=clean_filename, content_path=str(final_path),
                sha256=digest.hexdigest(), size_bytes=size, crs=effective_crs,
                data_role=data_role, summary=summary,
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


@app.get("/api/v1/crs/inspect")
def crs_inspection(crs: str) -> dict:
    """Validate and normalize a user-provided CRS definition."""
    from geologia.geospatial import inspect_crs

    try:
        return inspect_crs(crs)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/v1/datasets/{dataset_id}/reproject", status_code=201)
def dataset_reproject(dataset_id: str, body: ReprojectInput) -> dict:
    """Create a new reprojected GeoJSON dataset; never overwrite the source."""
    item = store.get_dataset(dataset_id)
    if item is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    if item["format"] not in {"geojson", "json"}:
        raise HTTPException(status_code=415, detail="reprojection supports GeoJSON only")
    content_path = store.get_dataset_content_path(dataset_id)
    if content_path is None or not Path(content_path).is_file():
        raise HTTPException(status_code=410, detail="dataset file is missing")
    try:
        payload = _read_json(Path(content_path))
    except (UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(
            status_code=422, detail="GeoJSON must be valid UTF-8 JSON with finite numbers"
        ) from exc
    try:
        metrics = inspect_geojson(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"invalid GeoJSON: {exc}") from exc
    source_crs = item["crs"] or "EPSG:4326"
    from geologia.geospatial import reproject_geojson

    try:
        transformed, info = reproject_geojson(payload, source_crs, body.target_crs)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    transformed_metrics = inspect_geojson(transformed)
    output_bytes = json.dumps(
        transformed, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    if len(output_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="reprojected dataset exceeds storage limit")
    storage = store.storage_path()
    temporary_path = None
    final_path = storage / f"{uuid4().hex}.blob"
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=storage, prefix=".reproject-", delete=False
        ) as tmp:
            temporary_path = Path(tmp.name)
            tmp.write(output_bytes)
        os.replace(temporary_path, final_path)
        derived_name = f"{item['name']} [{info['target_crs']}]"
        derived_name = derived_name[:120]
        original_filename = Path(item["original_filename"]).stem[:180]
        original_filename += ".reprojected.geojson"
        summary = {
            "validation": "structural_only",
            "feature_count": metrics["feature_count"],
            "derived_from_dataset_id": dataset_id,
            "operation": "geojson_reprojection",
            "coordinate_count": metrics["coordinate_count"],
            "bbox_xy": transformed_metrics["bbox_xy"],
            "source_crs": info["source_crs"],
            "target_crs": info["target_crs"],
            "scientific_interpretation": False,
        }
        try:
            dataset = store.create_dataset(
                item["project_id"], name=derived_name, file_format="geojson",
                original_filename=original_filename, content_path=str(final_path),
                sha256=hashlib.sha256(output_bytes).hexdigest(),
                size_bytes=len(output_bytes), crs=info["target_crs"],
                data_role=item["data_role"], summary=summary,
            )
        except Exception:
            final_path.unlink(missing_ok=True)
            raise
        return {
            "dataset": dataset,
            "operation": "geojson_reprojection",
            **info,
            "coordinate_count": metrics["coordinate_count"],
            "source_dataset_id": dataset_id,
            "source_dataset_modified": False,
        }
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


@app.get("/api/v1/datasets/{dataset_id}/geojson")
def dataset_geojson(dataset_id: str) -> JSONResponse:
    """Return validated GeoJSON only; never expose the private storage path."""
    item = store.get_dataset(dataset_id)
    if item is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    if item["format"] not in {"geojson", "json"}:
        raise HTTPException(status_code=415, detail="map view supports GeoJSON only")
    content_path = store.get_dataset_content_path(dataset_id)
    if content_path is None or not Path(content_path).is_file():
        raise HTTPException(status_code=410, detail="dataset file is missing")
    try:
        payload = _read_json(Path(content_path))
    except (UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(
            status_code=422, detail="GeoJSON must be valid UTF-8 JSON with finite numbers"
        ) from exc
    try:
        inspect_geojson(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    declared_crs = item["crs"] or "EPSG:4326"
    if declared_crs.upper() not in {"EPSG:4326", "OGC:CRS84"}:
        from geologia.geospatial import reproject_geojson

        try:
            payload, _ = reproject_geojson(payload, declared_crs, "EPSG:4326")
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    return JSONResponse(content=payload)


@app.post("/api/v1/datasets/{dataset_id}/inspect", status_code=200)
def dataset_inspect(dataset_id: str) -> dict:
    """Run bounded format-specific inspection; never claim scientific interpretation."""
    item = store.get_dataset(dataset_id)
    if item is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    content_path = store.get_dataset_content_path(dataset_id)
    if content_path is None or not Path(content_path).is_file():
        raise HTTPException(status_code=410, detail="dataset file is missing")

    file_format = item["format"]
    if file_format == "csv":
        try:
            report = inspect_csv(Path(content_path))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        operation = "csv_inspection"
    elif file_format in {"geojson", "json"}:
        try:
            payload = _read_json(Path(content_path))
        except (UnicodeDecodeError, ValueError) as exc:
            raise HTTPException(
                status_code=422, detail="GeoJSON must be valid UTF-8 JSON with finite numbers"
            ) from exc
        try:
            report = inspect_geojson(payload)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        operation = "geojson_inspection"
    elif file_format in {"gpkg", "tif", "tiff", "las"}:
        from geologia.formats import (
            FormatDependencyError,
            FormatValidationError,
            inspect_geopackage,
            inspect_geotiff,
            inspect_las,
        )

        inspectors = {
            "gpkg": inspect_geopackage,
            "tif": inspect_geotiff,
            "tiff": inspect_geotiff,
            "las": inspect_las,
        }
        try:
            report = inspectors[file_format](Path(content_path))
        except FormatDependencyError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except FormatValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        operation = f"{report['format']}_inspection"
    else:
        raise HTTPException(status_code=415, detail="inspection is not supported for this format")

    report.update({
        "dataset_id": dataset_id,
        "operation": operation,
        "scientific_interpretation": False,
    })
    store.save_dataset_inspection(dataset_id, report)
    return report


@app.post("/api/v1/projects/{project_id}/jobs", status_code=201)
def jobs_create(project_id: str, body: JobInput) -> dict:
    if store.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    plan = build_plan(body.request, body.language)
    available = store.list_dataset_roles(project_id)
    required = plan["required_inputs"]
    missing = sorted(set(required) - set(available))
    plan["data_readiness"] = {
        "available_inputs": available,
        "missing_inputs": missing,
        "required_roles_present": not missing,
        "content_validation": "not_performed",
        "execution_allowed": False,
        "execution_blocked_reason": "No scientific engine is integrated or certified.",
    }
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
    if args.host not in {"127.0.0.1", "::1", "localhost"}:
        parser.error(
            "remote binding is disabled in this development server; "
            "use loopback until authentication and production controls are implemented"
        )
    uvicorn.run("geologia.api:app", host=args.host, port=args.port, reload=False)


app.mount("/", StaticFiles(directory=Path(__file__).parent / "web", html=True), name="web")


if __name__ == "__main__":
    run()
