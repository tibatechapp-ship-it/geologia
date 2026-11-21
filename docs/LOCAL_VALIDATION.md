# Local validation record

Date: 2026-11-21

## Source package validation

The source bundle was cleaned, rebuilt from scratch, extracted into a fresh directory, and tested from that extracted copy.

- `python -m pytest`: **11 passed**.
- `python -m compileall -q apps/api/app tests`: **passed**.
- `python -m pip wheel . --no-deps --no-build-isolation`: wheel build passed.
- ZIP integrity: passed.
- Packaging inspection: no duplicate nested project folder, pytest cache, Python bytecode, or egg-info in the verified archive.
- Archive SHA-256: `04591914fb62f4fb10d1b508dfe0a0f7209c58e9df95b61e30ea38c75b63923c`.

Ruff was not available locally. Docker is not installed, so container build/runtime was not verified.

## Repository transfer status

The GitHub repository currently contains bootstrap documentation and this validation record. The full application source tree has **not yet been committed to GitHub**. The ZIP is a local artifact, not a repository release. Do not interpret the repository as a complete or deployable implementation until the source tree is transferred and GitHub CI passes.

## Known release blockers

- `LICENSE` in the source bundle is a placeholder, not the complete AGPL-3.0 text.
- The API is intended for local development and must not be exposed publicly without authentication, authorization, malware scanning, quotas, isolated workers, private storage, and monitoring.
- GeoPackage and GeoTIFF are registered only; no GIS worker is integrated.
- No scientific interpretation, resource probability, groundwater yield, or drilling recommendation is provided.
