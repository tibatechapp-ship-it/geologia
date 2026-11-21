# GEOLOGIA | جيولوجيا

**Bilingual open-source geoscience platform** — foundational Phase 0/1.

This repository is the starting foundation for GEOLOGIA and its planned chief agent, **المهندس الجمهوري**.

## Foundation scope
- FastAPI API and SQLite metadata store for local development
- Projects, dataset registration/upload, job status, and tool registry
- Safe structural GeoJSON summary (geometry counts and bounding box only)
- Validation gate and provenance manifest
- Automated CI workflow and tests

GeoPackage and GeoTIFF can be registered, but are not analyzed until isolated GDAL/GeoPandas/Rasterio workers are integrated. This foundation does **not** generate geological interpretations, groundwater-yield estimates, mineral probabilities, or drilling recommendations.

## Source status
The Phase 0/1 source package has been prepared and locally validated, but the application source tree has **not yet been transferred into this repository**. This repository currently contains bootstrap documentation and a validation record, not a runnable implementation. Track the remaining source-transfer and release work in [Issue #1](https://github.com/tibatechapp-ship-it/geologia/issues/1).

Local validation of the prepared package: **8 tests passed** and `compileall` passed. Ruff could not be run in the local environment because it is not installed; CI installs Ruff through the development dependencies.

## Planned quick start (after source transfer)
```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
uvicorn app.main:app --app-dir apps/api --reload
```

API docs: `http://127.0.0.1:8000/docs`

## Security and scientific limitations
Do not expose the development API publicly without authentication, authorization, malware scanning, quotas, private storage, isolated workers, and monitoring. Third-party engines are not bundled. See the source package's `docs/` directory for architecture, integration policy, scientific validation, security, data governance, and roadmap.

## License
The source package's `LICENSE` is currently a placeholder. Before public release, replace it with the complete official AGPL-3.0-or-later text and verify third-party notices.
