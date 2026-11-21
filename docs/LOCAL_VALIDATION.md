# Validation and repository status

Updated: 2026-11-21

## Source on GitHub

The runnable application source is committed to the default branch `main`.

## Latest verified CI

- Main-branch run [#44940098319](https://github.com/tibatechapp-ship-it/geologia/actions/runs/44940098319) passed after Ali Algomori's agent-core merge: Python 3.12, 3.14, and 3.15; 60 tests passed on Python 3.12, Ruff and compile checks passed.
- PWA PR #10 validation [#44939426012](https://github.com/tibatechapp-ship-it/geologia/actions/runs/44939426012) passed all three Python versions; 45 tests passed on Python 3.12.
- Local installer PR #11 validation [#44939710621](https://github.com/tibatechapp-ship-it/geologia/actions/runs/44939710621) passed all three Python versions; 51 tests passed on Python 3.12, including Bash syntax validation.
- Ali agent PR #12 validation [#44940027519](https://github.com/tibatechapp-ship-it/geologia/actions/runs/44940027519) passed all three Python versions; 60 tests passed on Python 3.12.

- Local knowledge PR #13 validation [#44940734988](https://github.com/tibatechapp-ship-it/geologia/actions/runs/44940734988) passed all three Python versions; 70 tests passed on Python 3.12.
- Desktop PR #14 validation [#44941262275](https://github.com/tibatechapp-ship-it/geologia/actions/runs/44941262275) passed all three Python versions; 73 tests passed on Python 3.12. Portable Windows, Linux, and macOS binaries passed packaged HTTP health, root-page, and manifest smoke checks.
- Main desktop build [#44941454934](https://github.com/tibatechapp-ship-it/geologia/actions/runs/44941454934) passed and uploaded three artifacts (Windows x64, Linux x64, macOS ARM64). Artifacts are retained for 30 days.
- Main CI after desktop merge [#44941454941](https://github.com/tibatechapp-ship-it/geologia/actions/runs/44941454941) passed the Python 3.12/3.14/3.15 matrix; 73 tests passed on Python 3.12.
- Main CI after core knowledge pack [#44942822111](https://github.com/tibatechapp-ship-it/geologia/actions/runs/44942822111) passed all three Python versions; 78 tests passed on Python 3.12.
- Main portable desktop artifacts [#44942822099](https://github.com/tibatechapp-ship-it/geologia/actions/runs/44942822099) passed on Windows x64, Linux x64, and macOS ARM64; artifact sizes were approximately 16.4 MB, 30.9 MB, and 15.0 MB respectively (30-day retention).
- Multilingual research-sync PR #17 [#44943072702](https://github.com/tibatechapp-ship-it/geologia/actions/runs/44943072702) passed all three Python versions; 82 tests passed on Python 3.12.
- Live Crossref synchronization was not manually dispatched during this validation; the PR validates query logic and language handling with unit tests. Provider availability and candidate volume remain subject to the scheduled/manual workflow.

## Implemented

- Phase 1: FastAPI, SQLite projects/jobs, deterministic plan records.
- Phase 2: bounded streaming dataset intake, generated storage paths, SHA-256, strict JSON and structural GeoJSON validation.
- Phase 3: Ali Algomori deterministic local agent with Arabic/English evidence routing, heuristic confidence, multi-domain plans, and clarification instead of a silent GIS fallback.
- Phase 4: bilingual Arabic RTL / English LTR frontend for projects, dataset intake, and plan display.
- Phase 5: CRS inspection and GeoJSON reprojection using optional pyproj; derived datasets are stored without overwriting source datasets.
- Installable PWA manifest, SVG icon, service worker, and static-shell offline fallback; API responses are not cached by the service worker.
- Local installer and loopback launcher scripts for POSIX systems, Termux bootstrap, and Windows PowerShell.
- Termux:Widget one-tap shortcut with background start, health/status, and guarded stop scripts; physical Android testing remains outstanding.
- One-file portable desktop binaries built and smoke-tested on Windows x64, Linux x64, and macOS ARM64; artifacts are available from the linked GitHub Actions run.
- Ali agent status endpoint and explicit model-independent runtime contract.
- Local SQLite knowledge retrieval foundation with FTS5/token-scan fallback, explicit license-reviewed ingestion, SHA-256 deduplication, and source-attributed chunks; no model or auto-download.
- Built-in 24-note four-language GEOLOGIA core pack, auto-seeded locally on first search/status; no external publication text copied.
- CJK-aware FTS v2 indexes deterministic Chinese/Japanese/Korean bigrams and rebuilds from preserved chunks; no embeddings or model dependency.
- Crossref metadata discovery expanded to English, Arabic, Russian, and Chinese query groups; publication language is retained and all candidates remain human-review-only.
- Portable desktop artifacts are published by the main-branch build workflow; they are unsigned executables, not native installers.
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
- The index auto-seeds 24 original GEOLOGIA-authored Arabic/English/Russian/Chinese core checklists; the external source corpus remains empty until explicit license-reviewed ingestion. Local text-based PDF extraction is available through optional pypdf with a 20 MiB / 500-page cap and page locators; scanned-image OCR and automatic full-text downloads are not implemented.
- No worker queue, isolated engine containers, or LLM provider integration.
- Engine license reviews are pending individually; the platform license does not relicense third-party engines.
- GeoJSON checks are structural only, not complete OGC conformance, topology, or scientific validation.
