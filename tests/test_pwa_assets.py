import json
from pathlib import Path

WEB = Path(__file__).parents[1] / "src" / "geologia" / "web"


def test_manifest_declares_installable_standalone_app():
    manifest = json.loads((WEB / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert manifest["start_url"] == "/"
    assert manifest["scope"] == "/"
    assert manifest["display"] == "standalone"
    assert manifest["lang"] == "ar"
    assert manifest["dir"] == "rtl"
    assert manifest["theme_color"] == "#07111f"
    for icon in manifest["icons"]:
        assert icon["src"].startswith("/")
        assert (WEB / icon["src"].lstrip("/")).is_file()


def test_index_links_manifest_and_registers_service_worker():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    assert 'rel="manifest" href="/manifest.webmanifest"' in html
    assert 'href="/icon.svg"' in html
    assert 'navigator.serviceWorker.register("/service-worker.js")' in html


def test_service_worker_caches_shell_but_never_api_data():
    worker = (WEB / "service-worker.js").read_text(encoding="utf-8")
    assert '"/style.css"' in worker
    assert '"/app.js"' in worker
    assert 'url.pathname.startsWith("/api/") || url.pathname === "/health"' in worker
    assert "Project, dataset and job data are deliberately never cached" in worker
    assert 'caches.match("/")' in worker
