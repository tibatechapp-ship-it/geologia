from pathlib import Path
import subprocess

ROOT = Path(__file__).parents[1]
SCRIPTS = ROOT / "scripts"


def test_posix_installer_requires_supported_python_and_keeps_gis_optional():
    script = (SCRIPTS / "install-local.sh").read_text(encoding="utf-8")
    assert "sys.version_info >= (3, 12)" in script
    assert "pip install -e '.[pdf]'" in script
    assert "pip install -e '.[pdf,gis]'" in script
    assert "Unknown option" in script


def test_posix_launcher_is_loopback_only_and_validates_port():
    script = (SCRIPTS / "start-local.sh").read_text(encoding="utf-8")
    assert '--host 127.0.0.1 --port "$PORT"' in script
    assert "GEOLOGIA_PORT must be between 1 and 65535" in script
    assert ".venv/bin/geologia-api" in script


def test_all_posix_install_and_run_scripts_parse():
    for script in sorted(SCRIPTS.glob("*.sh")):
        subprocess.run(["bash", "-n", str(script)], check=True, capture_output=True, text=True)


def test_termux_bootstrap_is_explicit_and_model_free():
    script = (SCRIPTS / "install-termux.sh").read_text(encoding="utf-8")
    assert 'TERMUX_VERSION' in script
    assert "pkg install -y python git clang rust make pkg-config" in script
    assert "bash scripts/install-local.sh" in script
    assert "do not expose it to the network" in script
    assert '$HOME/.shortcuts' in script
    assert "termux-widget-start.sh" in script
    assert "chmod 700" in script


def test_windows_installer_and_launcher_bind_to_loopback():
    installer = (SCRIPTS / "install-windows.ps1").read_text(encoding="utf-8")
    launcher = (SCRIPTS / "start-windows.ps1").read_text(encoding="utf-8")
    assert "sys.version_info >= (3,12)" in installer
    assert ".[pdf,gis]" in installer
    assert '{ $PackageSpec }' not in installer
    assert 'else { ".[pdf]" }' in installer
    assert "--host 127.0.0.1 --port $Port" in launcher
    assert "ValidateRange(1, 65535)" in launcher


def test_local_install_document_does_not_claim_native_package():
    doc = (ROOT / "docs" / "LOCAL_INSTALL.md").read_text(encoding="utf-8")
    assert "no native APK is built" in doc
    assert "unsigned portable binaries" in doc
    assert "Termux has not yet been validated" in doc


def test_termux_widget_launcher_is_local_and_health_checked():
    start = (SCRIPTS / "termux-widget-start.sh").read_text(encoding="utf-8")
    stop = (SCRIPTS / "termux-widget-stop.sh").read_text(encoding="utf-8")
    status = (SCRIPTS / "termux-widget-status.sh").read_text(encoding="utf-8")
    assert '--host 127.0.0.1 --port "$PORT"' in start
    assert "is_geologia_healthy" in start
    assert "nohup" in start
    assert "termux-open-url" in start
    assert "/proc/$PID/cmdline" in stop
    assert "CMDLINE=" in stop
    assert "refusing to terminate it" in stop
    assert "127.0.0.1" in status
