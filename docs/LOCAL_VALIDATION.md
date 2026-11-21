# Validation and repository status

Updated: 2026-11-21

## Source on GitHub

The runnable application source is committed to the default branch `main`.

## Latest verified CI

- Main-branch run [#44939490958](https://github.com/tibatechapp-ship-it/geologia/actions/runs/44939490958) passed after the PWA merge.
- PWA PR validation [#44939426012](https://github.com/tibatechapp-ship-it/geologia/actions/runs/44939426012) passed on commit `66f0b6cbe4e9d8cb6d00e2d0938ca128c82a773c`: Python 3.12, 3.14, and 3.15; 45 tests passed on Python 3.12, Ruff and compile checks passed.
- A first intermediate commit in the PWA branch failed because the new test arrived before the HTML manifest link; the link was added, and the final PR head passed. The failure was not hidden.

## Implemented

- Phase 1: FastAPI, SQLite projects/jobs, deterministic plan records.
- Phase 2: bounded streaming dataset intake, generated storage paths, SHA-256, strict JSON and structural GeoJSON validation.
- Phase 3: deterministic domain routing, specialist role labels, and required-role coverage reporting that explicitly does not claim content validation.
- Phase 4: bilingual Arabic RTL / English LTR frontend for projects, dataset intake, and plan display.
- Phase 5: CRS inspection and GeoJSON reprojection using optional pyproj; derived datasets are stored without overwriting source datasets.
- Installable PWA manifest, SVG icon, service worker, and static-shell offline fallback; API responses are not cached by the service worker.
- Local installer and loopback launcher scripts for POSIX systems, Termux bootstrap, and Windows PowerShell.
- 30 engine catalog cards, all `planned` and `license_status: unverified`.
- Root `LICENSE`: GNU AGPL v3.
- Full-history findings and remaining blockers: [ENGINEERING_AUDIT.md](ENGINEERING_AUDIT.md).

## Explicitly not verified or not implemented

- CI runs on GitHub-hosted Ubuntu; **Termux/Android installation has not been validated on a physical device**. The bootstrap may need native compilation for Pydantic dependencies.
- PWA browser installation on actual Android, Windows, macOS, and Linux devices is not yet cross-device certified.
- No signed native APK, MSI, DMG, or AppImage release.
- No production deployment or production authentication/authorization; keep the API bound to localhost.
- No scientific engine is integrated or certified; `engines_integrated` remains 0.
- GeoPackage, GeoTIFF, and LAS are stored only. CSV receives structural inspection; it is not scientifically interpreted.
- No worker queue, isolated engine containers, or LLM provider integration.
- Engine license reviews are pending individually; the platform license does not relicense third-party engines.
- GeoJSON checks are structural only, not complete OGC conformance, topology, or scientific validation.
