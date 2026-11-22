"""Run a packaged GEOLOGIA executable and verify its local HTTP shell."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.request import urlopen


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/smoke_desktop.py PATH_TO_EXECUTABLE")
    executable = Path(sys.argv[1]).resolve()
    if not executable.is_file():
        raise SystemExit(f"Desktop executable not found: {executable}")

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base_url = f"http://127.0.0.1:{port}"

    with tempfile.TemporaryDirectory(prefix="geologia-desktop-smoke-") as temp_dir:
        data_dir = Path(temp_dir)
        environment = os.environ.copy()
        environment["GEOLOGIA_DB_PATH"] = str(data_dir / "app.sqlite3")
        environment["GEOLOGIA_UPLOAD_DIR"] = str(data_dir / "uploads")
        environment["GEOLOGIA_KNOWLEDGE_DB_PATH"] = str(data_dir / "knowledge.sqlite3")
        process = subprocess.Popen(
            [str(executable), "--port", str(port), "--no-browser"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=environment,
        )
        try:
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    output = process.stdout.read() if process.stdout else ""
                    raise RuntimeError(f"Desktop process exited early:\n{output}")
                try:
                    with urlopen(f"{base_url}/health", timeout=1) as response:
                        if response.status != 200:
                            raise RuntimeError("health endpoint returned a non-200 status")
                    break
                except (URLError, TimeoutError):
                    time.sleep(0.25)
            else:
                raise RuntimeError("Desktop server did not start in time.")

            with urlopen(f"{base_url}/", timeout=3) as response:
                html = response.read()
                assert response.status == 200 and b"GEOLOGIA" in html
            with urlopen(f"{base_url}/manifest.webmanifest", timeout=3) as response:
                manifest = response.read()
                assert response.status == 200 and b"standalone" in manifest

            with urlopen(f"{base_url}/api/v1/knowledge/status", timeout=15) as response:
                knowledge_status = json.loads(response.read())
                assert response.status == 200
                assert knowledge_status["core_seeded_count"] == 24
                assert knowledge_status["model_required"] is False
        finally:
            if os.name == "nt":
                # The packaged Windows app can leave a worker holding SQLite
                # handles after the parent exits; terminate the full process tree.
                try:
                    subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        check=False,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=15,
                    )
                except (OSError, subprocess.TimeoutExpired):
                    pass
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            if process.stdout:
                process.stdout.close()

    print("Packaged GEOLOGIA server smoke test passed.")


if __name__ == "__main__":
    main()
