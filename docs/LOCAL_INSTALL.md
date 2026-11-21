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

## Safety and current limitations

- Launchers bind to `127.0.0.1`; they do not provide a public or LAN server.
- Do not change the bind address until authentication, authorization, tenant isolation, quotas, and worker security are implemented.
- This provides a local install workflow and browser-installable PWA, not a signed native APK or packaged desktop executable.
- Termux has not yet been validated on a physical Android device by this repository's CI. Record device, Android/Termux/Python versions, install output, and test results before declaring Android support stable.
- Installing the optional GIS extra is separate because pyproj and projection libraries may need native platform support.
