# Installable GEOLOGIA web app

GEOLOGIA now includes a Progressive Web App (PWA) shell. On a supported browser, served from HTTPS or localhost, users can install the workspace to the home screen or desktop app launcher.

## Included

- Web app manifest with standalone display metadata.
- Vector app icon.
- Service worker that caches the application shell and same-origin static assets.
- Offline navigation fallback to the cached workspace shell.
- Explicit network-only handling for `/api/*` and `/health`; user projects, datasets, and jobs are not cached by this service worker.

## Install

1. Install and run GEOLOGIA locally using the project's Quick Start.
2. Open the local workspace in a supported browser at `http://127.0.0.1:8000`.
3. Use the browser's **Install app** or **Add to Home screen** action when offered.

For a remote hosted copy, HTTPS is required for service-worker installation.

## Important limits

This is an installable web app shell, not a native Android APK, Windows MSI, macOS DMG, or Linux AppImage. Those native packages have not been built.

Offline mode caches the interface only. API operations require the GEOLOGIA local API to be running. Project and dataset contents are not placed into service-worker cache. The map currently depends on externally hosted Leaflet and map tiles, so the map is not guaranteed to work offline.

The manifest uses a vector SVG icon. Browser-specific installation behavior may vary; final Android/desktop package validation still requires real-device and browser testing.
