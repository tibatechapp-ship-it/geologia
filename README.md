# GEOLOGIA | جيولوجيا

**Bilingual open-source geoscience platform** — foundational Phase 0/1.

This repository is the starting foundation for GEOLOGIA and its planned chief agent, **المهندس الجمهوري**.

## Foundation scope
- FastAPI API and SQLite metadata store for local development
- Projects, dataset registration/upload, job status, and tool registry
- Safe structural GeoJSON summary (geometry counts and bounding box only)
- Validation gate and provenance manifest
- Automated CI workflow and tests in the prepared source package

GeoPackage and GeoTIFF can be registered, but are not analyzed until isolated GDAL/GeoPandas/Rasterio workers are integrated. This foundation does **not** generate geological interpretations, groundwater-yield estimates, mineral probabilities, or drilling recommendations.

## Source status
The Phase 0/1 source package has been prepared and validated locally, but the application source tree has **not yet been transferred into this repository**. This repository currently contains bootstrap documentation and a validation record, not a runnable implementation. Track source transfer and release readiness in [Issue #1](https://github.com/tibatechapp-ship-it/geologia/issues/1).

Latest local validation of the prepared package: **11 tests passed**, `compileall` passed, and a Python wheel built successfully. The package also includes a Dockerfile and a Compose configuration bound to localhost by default. Docker itself is not installed in the validation environment, so an actual container build/run has not been verified. Ruff is included in CI but was unavailable locally.

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
