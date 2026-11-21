# Local validation record

Date: 2026-11-21

## Source package validation

The source bundle was cleaned, rebuilt from scratch, extracted into a fresh directory, and tested from that extracted copy.

- `python -m pytest`: **11 passed**.
- `python -m compileall -q apps/api/app tests`: **passed**.
- `python -m pip wheel . --no-deps --no-build-isolation`: wheel build passed.
- ZIP integrity: passed.
- Packaging inspection: no duplicate nested project folder, pytest cache, Python bytecode, or egg-info in the verified archive.
- Local archive SHA-256: `59febf459fb9a59a47262afb43fbef81cec579a21e3de35ac86384a53004c08e`.

Ruff was not available locally. Docker is not installed, so container build/runtime was not verified.

## Repository transfer status

The default branch still contains bootstrap documentation and this validation record, not the application source tree. A separate `phase-0-1/source-transfer` branch now contains a guarded GitHub Actions workflow that will validate and unpack the verified bundle when the bundle is committed at `bootstrap/geologia-phase-0-1.zip`. The bundle has not yet been committed to that branch; the workflow has not run. The local ZIP is not a GitHub release.

## Known release blockers

- `LICENSE` in the source bundle is a placeholder, not the complete AGPL-3.0 text.
- The API is intended for local development and must not be exposed publicly without authentication, authorization, malware scanning, quotas, isolated workers, private storage, and monitoring.
- GeoPackage and GeoTIFF are registered only; no GIS worker is integrated.
- No scientific interpretation, resource probability, groundwater yield, or drilling recommendation is provided.
