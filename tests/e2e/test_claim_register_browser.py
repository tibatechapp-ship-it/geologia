from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

import pytest

playwright_sync = pytest.importorskip("playwright.sync_api")
sync_playwright = playwright_sync.sync_playwright


ROOT = Path(__file__).resolve().parents[2]


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_server(url: str, process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 25
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"GEOLOGIA server exited early: {process.returncode}")
        try:
            with urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except Exception as exc:  # server is still starting
            last_error = exc
        time.sleep(0.2)
    raise RuntimeError(f"GEOLOGIA server did not become ready: {last_error}")


def test_browser_claim_to_evidence_workflow(tmp_path, monkeypatch):
    from geologia import knowledge

    knowledge_db = tmp_path / "knowledge.sqlite3"
    app_db = tmp_path / "app.sqlite3"
    upload_dir = tmp_path / "uploads"
    monkeypatch.setenv("GEOLOGIA_KNOWLEDGE_DB_PATH", str(knowledge_db))
    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(app_db))
    monkeypatch.setenv("GEOLOGIA_UPLOAD_DIR", str(upload_dir))
    monkeypatch.setenv("GEOLOGIA_DISABLE_CORE_SEED", "1")

    source = tmp_path / "groundwater-study.txt"
    source.write_text(
        "Groundwater recharge may raise measured aquifer water levels "
        "under documented hydrogeological conditions.",
        encoding="utf-8",
    )
    knowledge.ingest_document(
        source,
        {
            "source_id": "browser-e2e-groundwater-001",
            "title": "Browser E2E groundwater evidence",
            "author": "GEOLOGIA test fixture",
            "publisher": "GEOLOGIA test fixture",
            "source_url": "https://example.org/groundwater-study",
            "license_name": "CC BY 4.0",
            "license_status": "open_license",
            "reviewed_by": "test rights reviewer",
            "review_date": "2026-11-22",
            "language": "en",
            "source_kind": "research_article",
            "scientific_review_status": "peer_reviewed",
            "scientific_reviewed_by": "test bibliographic reviewer",
            "scientific_review_date": "2026-11-22",
            "scientific_review_basis": "https://example.org/review-record",
        },
    )

    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    environment = os.environ.copy()
    environment.update(
        {
            "GEOLOGIA_KNOWLEDGE_DB_PATH": str(knowledge_db),
            "GEOLOGIA_DB_PATH": str(app_db),
            "GEOLOGIA_UPLOAD_DIR": str(upload_dir),
            "GEOLOGIA_DISABLE_CORE_SEED": "1",
        }
    )
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "geologia.api:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "error",
        ],
        cwd=ROOT,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        _wait_for_server(f"{base_url}/health", process)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page()
            page_errors: list[str] = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.goto(base_url, wait_until="domcontentloaded")

            page.locator("#projectName").fill("Validation browser project")
            page.locator("#projectForm button[type=submit]").click()
            page.wait_for_function(
                "document.querySelector('#projectSelect').value !== ''",
                timeout=10000,
            )
            csv_path = tmp_path / "water-levels.csv"
            csv_path.write_text(
                "timestamp,water_level_m\\n2026-01-01,12.4\\n",
                encoding="utf-8",
            )
            page.locator("#datasetName").fill("Groundwater levels")
            page.locator("#dataRole").select_option("water_levels_timeseries")
            page.locator("#fileInput").set_input_files(str(csv_path))
            page.locator("#datasetForm button[type=submit]").click()
            dataset_item = page.locator("#datasetList .dataset-item").filter(
                has_text="Groundwater levels"
            )
            dataset_item.wait_for(state="visible", timeout=10000)
            dataset_item.locator("button.validation-button").click()
            validation_report = dataset_item.locator("pre.validation-report")
            validation_report.wait_for(state="visible", timeout=10000)
            assert '"validation_status": "passed"' in validation_report.inner_text()

            claim_statement = "Recharge increased the observed groundwater level."
            page.locator("#claimStatement").fill(claim_statement)
            page.locator("#claimRecorder").fill("browser test geologist")
            page.locator("#claimForm button[type=submit]").click()
            claim_item = page.locator(".claim-list-item").filter(
                has_text=claim_statement
            )
            claim_item.wait_for(state="visible", timeout=10000)

            page.locator("#claimEvidenceQuery").fill("groundwater recharge")
            page.locator("#claimEvidenceSearch button[type=submit]").click()
            result = page.locator(".claim-search-result").filter(
                has_text="Browser E2E groundwater evidence"
            )
            result.wait_for(state="visible", timeout=10000)
            form = result.locator(".claim-link-form")
            form.locator("select").select_option("supports")
            form.locator("textarea").fill(
                "The excerpt describes recharge and a possible measured water-level rise."
            )
            form.locator("input").fill("browser evidence reviewer")
            form.locator('button[type="submit"]').click()

            linked = page.locator("#claimEvidenceLinked .claim-evidence-card")
            linked.wait_for(state="visible", timeout=10000)
            linked_text = linked.inner_text()
            assert "Groundwater recharge may raise measured aquifer water levels" in linked_text
            assert "The excerpt describes recharge" in linked.inner_text()
            basis = linked.locator('a[href="https://example.org/review-record"]')
            basis.wait_for(state="visible")
            assert basis.get_attribute("rel") == "noopener noreferrer"
            with urlopen(base_url + "/api/v1/knowledge/claims?limit=100", timeout=2) as response:
                register = json.loads(response.read())
            saved_claim = next(
                item for item in register["claims"]
                if item["statement"] == claim_statement
            )
            detail_url = base_url + "/api/v1/knowledge/claims/" + saved_claim["claim_id"]
            with urlopen(detail_url, timeout=2) as response:
                detail = json.loads(response.read())
            assert detail["evidence_annotations"][0]["relation"] == "supports"
            assert detail["evidence_annotations"][0]["recorded_by"] == "browser evidence reviewer"
            assert page_errors == []
            browser.close()
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
