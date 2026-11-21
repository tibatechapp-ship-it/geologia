# Local installation: desktop and Android Termux

GEOLOGIA is a local Python application. Its core runtime does not download or require a large language model, model weights, a paid AI API, or a remote inference service.

The scripts below install the application into a project-local virtual environment and bind the API to loopback only.

## Linux and macOS

Install Python 3.12 or newer, download/clone the repository, then run from its root:

```bash
bash scripts/install-local.sh
bash scripts/start-local.sh
```

Open `http://127.0.0.1:8000`. To choose another port:

```bash
GEOLOGIA_PORT=8123 bash scripts/start-local.sh
```

Optional coordinate reference system tools can be installed separately:

```bash
bash scripts/install-local.sh --gis
```

The GIS extra is optional and may require platform-specific native libraries.

## Android with Termux

1. Install Termux from a trusted distribution source.
2. Download or clone the GEOLOGIA repository into Termux.
3. From the repository root, run:

```bash
bash scripts/install-termux.sh
bash scripts/start-local.sh
```

The bootstrap installs Python and a native build toolchain because some Python dependencies may need to compile on Android. This is a one-time installation cost; no model weights are installed. Compilation duration and memory use vary by device. The GIS extra is intentionally not installed by default.

The installer creates `~/.shortcuts/GEOLOGIA`. Install the **Termux:Widget** companion from the same trusted distribution source, then add the GEOLOGIA shortcut widget to the home screen. Tapping it starts the API in the background and opens the local workspace. The PID and log are stored under `~/.geologia`.

To stop or inspect the server:

```bash
bash scripts/termux-widget-stop.sh
bash scripts/termux-widget-status.sh
```

The launcher checks the local health endpoint, binds only to `127.0.0.1`, and refuses to terminate a process whose command line cannot be identified as GEOLOGIA. Android battery management may still stop background processes; disable battery optimization for Termux only if needed and understood.

Open `http://127.0.0.1:8000` in the Android browser. The PWA can then be added to the home screen when supported.

## Windows

Run PowerShell from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-windows.ps1
powershell -ExecutionPolicy Bypass -File scripts\start-windows.ps1
```

Optional GIS dependencies:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-windows.ps1 -GIS
```

## Portable desktop executable

The [desktop build workflow](https://github.com/tibatechapp-ship-it/geologia/actions/workflows/desktop-build.yml) creates one-file executables for Windows, Linux, and macOS. After a successful run, download the matching artifact from the workflow run's **Artifacts** section. The artifact contains the executable only and is retained for 30 days.

The executable binds only to `127.0.0.1`, opens the browser when the server is ready, and keeps the database, uploads, and local knowledge index under `~/.geologia` (or the user's home equivalent). Override the port with `--port 8123`.

These are unsigned portable binaries, not signed native installers. Windows SmartScreen and macOS Gatekeeper may warn because the binaries are not code-signed. Android is still Termux + PWA; there is no native APK in this repository.

## Local knowledge pack

The first knowledge search or status request indexes 24 original GEOLOGIA-authored checklists in Arabic, English, Russian, and Chinese across six geoscience domains. This is a lightweight local retrieval pack, not neural training and not copied full-text publications. Install scripts include the lightweight `pypdf` extra for local text-based PDF ingestion; files are limited to 20 MiB and 500 pages, and citations retain page numbers. Scanned PDFs require OCR elsewhere before ingestion; GEOLOGIA does not run OCR. External documents are indexed only after explicit source/license review. See [the source/license matrix](ALI_SOURCE_LICENSE_MATRIX.md).

Search the index from the terminal without opening the browser:

```bash
geologia-knowledge --search "groundwater recharge" --limit 5
```

The command prints JSON with source metadata, citation locators, and lexical evidence coverage. It performs local retrieval only; coverage is not scientific confidence.

## Safety and current limitations

- Launchers bind to `127.0.0.1`; they do not provide a public or LAN server.
- Do not change the bind address until authentication, authorization, tenant isolation, quotas, and worker security are implemented.
- Android remains Termux + PWA; no native APK is built. Desktop has unsigned portable one-file binaries, not signed MSI/DMG/AppImage installers.
- Termux has not yet been validated on a physical Android device by this repository's CI. Record device, Android/Termux/Python versions, install output, and test results before declaring Android support stable.
- Installing the optional GIS extra is separate because pyproj and projection libraries may need native platform support.
