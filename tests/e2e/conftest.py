"""Shared real-browser fixtures for GEOLOGIA end-to-end tests."""
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

sync_playwright = pytest.importorskip("playwright.sync_api").sync_playwright

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def app_url(tmp_path_factory):
    runtime = tmp_path_factory.mktemp("geologia-e2e")
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    env = os.environ.copy()
    env["GEOLOGIA_DB_PATH"] = str(runtime / "geologia.sqlite3")
    env["GEOLOGIA_UPLOAD_DIR"] = str(runtime / "uploads")
    process = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn", "geologia.api:app",
            "--host", "127.0.0.1", "--port", str(port),
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("GEOLOGIA API process exited before becoming healthy")
        try:
            with urllib.request.urlopen(f"{url}/health", timeout=1) as response:
                if response.status == 200:
                    break
        except (OSError, urllib.error.URLError):
            time.sleep(0.2)
    else:
        process.terminate()
        raise RuntimeError("GEOLOGIA API did not become healthy within 30 seconds")

    yield url

    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


@pytest.fixture
def browser_page():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.route("https://unpkg.com/**", lambda route: route.abort())
        yield page
        browser.close()
