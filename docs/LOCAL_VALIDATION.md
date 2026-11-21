# Local validation record

Date: 2026-11-21

## Source package validation

The Phase 0/1 package was extracted and validated locally.

- `python -m pytest`: **8 passed** (after configuring pytest's `pythonpath` to include `apps/api`).
- `python -m compileall -q apps/api/app tests`: **passed**.
- `ruff check .`: not run successfully in this environment because Ruff is not installed; CI installs Ruff from the development extra.

## Repository transfer status

The GitHub repository currently contains the bootstrap README and this validation record. The full application source archive is not yet committed to GitHub. Do not interpret this repository as a complete or deployable implementation until the source tree is transferred and CI passes.

## Known release blockers

- `LICENSE` in the source archive is a placeholder, not the complete AGPL-3.0 text.
- The API is intended for local development and must not be exposed publicly without authentication, authorization, malware scanning, quotas, isolated workers, private storage, and monitoring.
- GeoPackage and GeoTIFF are registered only; no GIS worker is integrated.
- No scientific interpretation, resource probability, groundwater yield, or drilling recommendation is provided.
