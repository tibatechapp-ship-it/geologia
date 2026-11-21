# GEOLOGIA | جيولوجيا

**Bilingual open-source geoscience platform** — foundational Phase 0/1.

This repository is the starting foundation for GEOLOGIA and its planned chief agent, **المهندس الجمهوري**.

## Foundation scope
- FastAPI API and SQLite metadata store for local development
- Projects, dataset registration/upload, job status, and tool registry
- Safe structural GeoJSON summary (geometry counts and bounding box only)
- Validation gate and provenance manifest
- Automated CI workflow and tests

GeoPackage and GeoTIFF files can be registered, but are not analyzed until isolated GDAL/GeoPandas/Rasterio workers are integrated. This foundation does **not** generate geological interpretations, groundwater-yield estimates, mineral probabilities, or drilling recommendations.

## Source package
The complete Phase 0/1 source package is provided in `geologia-phase-0-1.zip` (to be added in the initial source upload).

## Quick start
```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
uvicorn app.main:app --app-dir apps/api --reload
```

API docs: `http://127.0.0.1:8000/docs`

## Security and scientific limitations
Do not expose the development API publicly without authentication, authorization, malware scanning, quotas, private storage, isolated workers, and monitoring. Third-party engines are not bundled. See `docs/` for architecture, integration policy, scientific validation, security, data governance, and roadmap.

## License
AGPL-3.0-or-later. Before public release, ensure the repository contains the complete official AGPL-3.0 license text and verify third-party notices.
